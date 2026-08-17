from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.research.auron_research_adapter_onboarding_v21_556 import (
    ResearchAdapterOnboardingPolicy,
    ResearchProviderBoundary,
)
from app.research.auron_research_registry_evidence_v21_557 import (
    ResearchQuery,
    ResearchRegistryEvidenceStore,
    ResearchResult,
    ResearchSource,
)


class ResearchReadIntegrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderSearchHit:
    provider_source_ref: str
    url: str
    title: str
    snippet: str
    rank: int


@dataclass(frozen=True)
class ProviderFetchedDocument:
    provider_source_ref: str
    url: str
    title: str
    content: str
    attribution: str
    publisher: str | None
    published_at: str | None
    retrieved_at: str


@dataclass(frozen=True)
class ResearchSyncRecord:
    query_id: str
    provider_id: str
    provider_source_ref: str
    source_id: str
    result_id: str
    observed_at: str
    external_calls_made: int


@dataclass(frozen=True)
class ResearchSyncSummary:
    query: ResearchQuery
    sources: tuple[ResearchSource, ...]
    results: tuple[ResearchResult, ...]
    sync_records: tuple[ResearchSyncRecord, ...]
    state: str
    external_calls_made: int
    downstream_actions_made: int = 0


class ResearchReadSearchFetchProvider(ResearchProviderBoundary, Protocol):
    def search(self, query_text: str, *, limit: int) -> tuple[ProviderSearchHit, ...]: ...
    def fetch(self, provider_source_ref: str) -> ProviderFetchedDocument: ...


class ResearchReadSearchFetchIntegration:
    """D11 certified read/search/fetch integration into the D10 evidence registry.

    Every provider is re-certified by D9 before a read operation. Search hits are not
    persisted as trusted evidence until the referenced document is fetched, identity
    checked and normalized into D10. This layer cannot trigger any downstream action.
    """

    def __init__(self, db_path: str | Path, registry: ResearchRegistryEvidenceStore,
                 onboarding: ResearchAdapterOnboardingPolicy | None = None) -> None:
        self.db_path = str(db_path)
        self.registry = registry
        self.onboarding = onboarding or ResearchAdapterOnboardingPolicy()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS research_provider_sync (
                query_id TEXT NOT NULL, provider_id TEXT NOT NULL,
                provider_source_ref TEXT NOT NULL, source_id TEXT NOT NULL,
                result_id TEXT NOT NULL, observed_at TEXT NOT NULL,
                external_calls_made INTEGER NOT NULL,
                PRIMARY KEY(query_id, provider_source_ref))''')

    def run_query(self, provider: ResearchReadSearchFetchProvider, query_text: str,
                  *, limit: int = 10, requested_at: str | None = None) -> ResearchSyncSummary:
        if limit < 1 or limit > 100:
            raise ResearchReadIntegrationError('limit must be between 1 and 100')

        decision = self.onboarding.require_onboarded(self.onboarding.evaluate(provider))
        if decision.allowed_mode not in {'read-only', 'simulation'}:
            raise ResearchReadIntegrationError('provider is not certified for governed reads')
        provider_id = decision.provider_id
        query = self.registry.record_query(query_text, provider_id, requested_at=requested_at)
        calls = decision.external_calls_made

        try:
            hits = provider.search(query.query_text, limit=limit)
            calls += 1
        except Exception as exc:
            raise ResearchReadIntegrationError('provider search failed') from exc

        sources: list[ResearchSource] = []
        results: list[ResearchResult] = []
        syncs: list[ResearchSyncRecord] = []
        seen_refs: set[str] = set()

        for hit in hits[:limit]:
            ref = hit.provider_source_ref.strip()
            if not ref or ref in seen_refs:
                raise ResearchReadIntegrationError('provider source refs must be non-empty and unique')
            seen_refs.add(ref)
            if hit.rank < 1 or not hit.url.strip() or not hit.title.strip() or not hit.snippet.strip():
                raise ResearchReadIntegrationError('provider search hit is incomplete')

            try:
                document = provider.fetch(ref)
                calls += 1
            except Exception as exc:
                raise ResearchReadIntegrationError(f'provider fetch failed for {ref}') from exc

            if document.provider_source_ref != ref:
                raise ResearchReadIntegrationError('provider source identity mismatch')
            if self.registry.canonicalize_url(document.url) != self.registry.canonicalize_url(hit.url):
                raise ResearchReadIntegrationError('search/fetch URL mismatch')
            if not document.attribution.strip() or not document.content:
                raise ResearchReadIntegrationError('fetched document lacks attribution or content')

            source = self.registry.upsert_source(
                provider_id=provider_id,
                url=document.url,
                title=document.title or hit.title,
                content=document.content,
                attribution=document.attribution,
                publisher=document.publisher,
                published_at=document.published_at,
                retrieved_at=document.retrieved_at,
            )
            result = self.registry.record_result(
                query.query_id,
                source.source_id,
                rank=hit.rank,
                snippet=hit.snippet,
                observed_at=document.retrieved_at,
            )
            sync = ResearchSyncRecord(
                query.query_id, provider_id, ref, source.source_id, result.result_id,
                document.retrieved_at, 1,
            )
            self._persist_sync(sync)
            sources.append(source)
            results.append(result)
            syncs.append(sync)

        state = 'read-sync-complete' if syncs else 'read-sync-empty'
        return ResearchSyncSummary(query, tuple(sources), tuple(results), tuple(syncs), state, calls, 0)

    def _persist_sync(self, record: ResearchSyncRecord) -> None:
        with self._connect() as conn:
            conn.execute('''INSERT INTO research_provider_sync VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(query_id,provider_source_ref) DO UPDATE SET
                provider_id=excluded.provider_id,source_id=excluded.source_id,
                result_id=excluded.result_id,observed_at=excluded.observed_at,
                external_calls_made=excluded.external_calls_made''', tuple(record.__dict__.values()))

    def list_sync_records(self, query_id: str) -> tuple[ResearchSyncRecord, ...]:
        with self._connect() as conn:
            rows = conn.execute('''SELECT * FROM research_provider_sync WHERE query_id=?
                                   ORDER BY observed_at, provider_source_ref''', (query_id,)).fetchall()
        return tuple(ResearchSyncRecord(**dict(row)) for row in rows)
