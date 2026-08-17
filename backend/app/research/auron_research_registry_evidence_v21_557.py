from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


class ResearchRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchSource:
    source_id: str
    provider_id: str
    canonical_url: str
    title: str
    publisher: str | None
    published_at: str | None
    retrieved_at: str
    content_hash: str
    attribution: str


@dataclass(frozen=True)
class ResearchQuery:
    query_id: str
    query_text: str
    provider_id: str
    requested_at: str
    state: str = 'recorded'


@dataclass(frozen=True)
class ResearchResult:
    result_id: str
    query_id: str
    source_id: str
    rank: int
    snippet: str
    evidence_hash: str
    observed_at: str


@dataclass(frozen=True)
class EvidenceState:
    source_id: str
    content_hash: str
    freshness_state: str
    age_seconds: int
    observed_at: str


class ResearchRegistryEvidenceStore:
    """D10 persistent normalized research registry.

    Stable IDs are derived from provider/query/source identity. Evidence hashes bind
    snippets to the source content hash so later synthesis can detect stale or changed
    evidence rather than silently reusing it.
    """

    def __init__(self, db_path: str | Path, *, fresh_for_seconds: int = 3600,
                 stale_after_seconds: int = 86400) -> None:
        if fresh_for_seconds < 0 or stale_after_seconds < fresh_for_seconds:
            raise ValueError('invalid freshness thresholds')
        self.db_path = str(db_path)
        self.fresh_for_seconds = fresh_for_seconds
        self.stale_after_seconds = stale_after_seconds
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _stable_id(prefix: str, *parts: str) -> str:
        raw = '\x1f'.join(parts).encode('utf-8')
        return f'{prefix}-{hashlib.sha256(raw).hexdigest()[:24]}'

    @staticmethod
    def canonicalize_url(url: str) -> str:
        value = url.strip()
        parts = urlsplit(value)
        if parts.scheme.lower() not in {'http', 'https'} or not parts.netloc:
            raise ResearchRegistryError('source URL must be absolute http(s)')
        host = parts.netloc.lower()
        path = parts.path or '/'
        return urlunsplit((parts.scheme.lower(), host, path, parts.query, ''))

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS research_sources (
                    source_id TEXT PRIMARY KEY, provider_id TEXT NOT NULL,
                    canonical_url TEXT NOT NULL, title TEXT NOT NULL,
                    publisher TEXT, published_at TEXT, retrieved_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL, attribution TEXT NOT NULL,
                    UNIQUE(provider_id, canonical_url));
                CREATE TABLE IF NOT EXISTS research_queries (
                    query_id TEXT PRIMARY KEY, query_text TEXT NOT NULL,
                    provider_id TEXT NOT NULL, requested_at TEXT NOT NULL,
                    state TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS research_results (
                    result_id TEXT PRIMARY KEY, query_id TEXT NOT NULL,
                    source_id TEXT NOT NULL, rank INTEGER NOT NULL,
                    snippet TEXT NOT NULL, evidence_hash TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY(query_id) REFERENCES research_queries(query_id),
                    FOREIGN KEY(source_id) REFERENCES research_sources(source_id),
                    UNIQUE(query_id, source_id));
                CREATE TABLE IF NOT EXISTS research_evidence_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL, observed_at TEXT NOT NULL);
            ''')

    def record_query(self, query_text: str, provider_id: str, *, requested_at: str | None = None) -> ResearchQuery:
        text, provider = query_text.strip(), provider_id.strip()
        if not text or not provider:
            raise ResearchRegistryError('query text and provider are required')
        at = requested_at or self._now()
        query_id = self._stable_id('qry', provider, text, at)
        query = ResearchQuery(query_id, text, provider, at)
        with self._connect() as conn:
            conn.execute('INSERT OR IGNORE INTO research_queries VALUES (?,?,?,?,?)', tuple(query.__dict__.values()))
        return query

    def upsert_source(self, *, provider_id: str, url: str, title: str, content: str,
                      attribution: str, publisher: str | None = None,
                      published_at: str | None = None, retrieved_at: str | None = None) -> ResearchSource:
        provider, heading, credit = provider_id.strip(), title.strip(), attribution.strip()
        if not provider or not heading or not credit:
            raise ResearchRegistryError('provider, title and attribution are required')
        canonical = self.canonicalize_url(url)
        at = retrieved_at or self._now()
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        source_id = self._stable_id('src', provider, canonical)
        source = ResearchSource(source_id, provider, canonical, heading, publisher, published_at, at, content_hash, credit)
        with self._connect() as conn:
            conn.execute('''INSERT INTO research_sources VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source_id) DO UPDATE SET title=excluded.title,publisher=excluded.publisher,
                published_at=excluded.published_at,retrieved_at=excluded.retrieved_at,
                content_hash=excluded.content_hash,attribution=excluded.attribution''', tuple(source.__dict__.values()))
            conn.execute('INSERT INTO research_evidence_history(source_id,content_hash,observed_at) VALUES (?,?,?)',
                         (source_id, content_hash, at))
        return source

    def record_result(self, query_id: str, source_id: str, *, rank: int, snippet: str,
                      observed_at: str | None = None) -> ResearchResult:
        query = self.get_query(query_id)
        source = self.get_source(source_id)
        if query is None or source is None:
            raise ResearchRegistryError('query and source must exist')
        if query.provider_id != source.provider_id:
            raise ResearchRegistryError('query/source provider mismatch')
        if rank < 1 or not snippet.strip():
            raise ResearchRegistryError('rank >= 1 and snippet are required')
        at = observed_at or self._now()
        evidence_hash = hashlib.sha256(f'{source.content_hash}\x1f{snippet.strip()}'.encode()).hexdigest()
        result_id = self._stable_id('res', query_id, source_id)
        result = ResearchResult(result_id, query_id, source_id, rank, snippet.strip(), evidence_hash, at)
        with self._connect() as conn:
            conn.execute('''INSERT INTO research_results VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(result_id) DO UPDATE SET rank=excluded.rank,snippet=excluded.snippet,
                evidence_hash=excluded.evidence_hash,observed_at=excluded.observed_at''', tuple(result.__dict__.values()))
        return result

    def evidence_state(self, source_id: str, *, now: str | None = None) -> EvidenceState:
        source = self.get_source(source_id)
        if source is None:
            raise ResearchRegistryError('source not found')
        current = datetime.fromisoformat(now or self._now())
        retrieved = datetime.fromisoformat(source.retrieved_at)
        age = max(0, int((current - retrieved).total_seconds()))
        if age <= self.fresh_for_seconds:
            state = 'fresh'
        elif age <= self.stale_after_seconds:
            state = 'aging'
        else:
            state = 'stale'
        return EvidenceState(source.source_id, source.content_hash, state, age, now or self._now())

    def get_source(self, source_id: str) -> ResearchSource | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM research_sources WHERE source_id=?', (source_id,)).fetchone()
        return ResearchSource(**dict(row)) if row else None

    def get_query(self, query_id: str) -> ResearchQuery | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM research_queries WHERE query_id=?', (query_id,)).fetchone()
        return ResearchQuery(**dict(row)) if row else None

    def list_results(self, query_id: str) -> tuple[ResearchResult, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM research_results WHERE query_id=? ORDER BY rank,result_id', (query_id,)).fetchall()
        return tuple(ResearchResult(**dict(row)) for row in rows)

    def source_history(self, source_id: str) -> tuple[dict, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT content_hash,observed_at FROM research_evidence_history WHERE source_id=? ORDER BY id', (source_id,)).fetchall()
        return tuple(dict(row) for row in rows)
