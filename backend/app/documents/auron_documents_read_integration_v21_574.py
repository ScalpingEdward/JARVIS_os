from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from app.documents.auron_documents_adapter_onboarding_v21_572 import DocumentsAdapterOnboardingPolicy, DocumentsProviderBoundary
from app.documents.auron_documents_registry_state_v21_573 import DocumentsRegistryStateStore, DocumentItem, DocumentVersion


class DocumentsReadIntegrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderItemObservation:
    provider_id: str
    provider_item_ref: str
    kind: str
    name: str
    parent_provider_item_ref: str | None = None
    mime_type: str | None = None
    state: str = 'active'
    metadata: dict | None = None
    provider_version_ref: str | None = None
    content_hash: str | None = None
    size_bytes: int | None = None
    modified_at: str | None = None


@dataclass(frozen=True)
class ProviderContentFetch:
    provider_id: str
    provider_item_ref: str
    provider_version_ref: str
    content: bytes
    content_hash: str | None = None


class DocumentsReadProvider(DocumentsProviderBoundary, Protocol):
    def list_items(self, parent_ref: str | None = None) -> tuple[ProviderItemObservation, ...]: ...
    def search_items(self, query: str) -> tuple[ProviderItemObservation, ...]: ...
    def fetch_content(self, provider_item_ref: str, provider_version_ref: str) -> ProviderContentFetch: ...


class DocumentsReadIntegration:
    """D27 certified read/list/search/fetch boundary feeding D26 normalized state."""

    def __init__(self, registry: DocumentsRegistryStateStore,
                 onboarding: DocumentsAdapterOnboardingPolicy | None = None) -> None:
        self.registry = registry
        self.onboarding = onboarding or DocumentsAdapterOnboardingPolicy()

    def _certify(self, provider: DocumentsReadProvider):
        return self.onboarding.require_onboarded(self.onboarding.evaluate(provider))

    def _ingest(self, observations: tuple[ProviderItemObservation, ...]) -> tuple[DocumentItem, ...]:
        pending = list(observations)
        ingested: list[DocumentItem] = []
        while pending:
            progressed = False
            for obs in tuple(pending):
                parent_id = None
                if obs.parent_provider_item_ref:
                    parent = self.registry.get_item_by_provider_ref(obs.provider_id, obs.parent_provider_item_ref)
                    if parent is None:
                        continue
                    parent_id = parent.item_id
                item = self.registry.observe_item(
                    provider_id=obs.provider_id, provider_item_ref=obs.provider_item_ref,
                    kind=obs.kind, name=obs.name, parent_item_id=parent_id,
                    mime_type=obs.mime_type, state=obs.state, metadata=obs.metadata,
                )
                if obs.kind == 'file' and obs.provider_version_ref:
                    self.registry.observe_version(
                        item_id=item.item_id, provider_version_ref=obs.provider_version_ref,
                        content_hash=obs.content_hash, size_bytes=obs.size_bytes,
                        modified_at=obs.modified_at,
                    )
                ingested.append(self.registry.get_item(item.item_id) or item)
                pending.remove(obs)
                progressed = True
            if not progressed:
                raise DocumentsReadIntegrationError('unresolved parent references in provider observations')
        return tuple(ingested)

    def list_and_sync(self, provider: DocumentsReadProvider, parent_ref: str | None = None) -> dict:
        decision = self._certify(provider)
        observations = provider.list_items(parent_ref)
        self._verify_provider_identity(decision.provider_id, observations)
        return {'items': self._ingest(observations), 'external_calls_made': decision.external_calls_made + 1,
                'write_enabled': False, 'delete_enabled': False}

    def search_and_sync(self, provider: DocumentsReadProvider, query: str) -> dict:
        if not query.strip():
            raise DocumentsReadIntegrationError('search query is required')
        decision = self._certify(provider)
        observations = provider.search_items(query.strip())
        self._verify_provider_identity(decision.provider_id, observations)
        return {'items': self._ingest(observations), 'external_calls_made': decision.external_calls_made + 1,
                'write_enabled': False, 'delete_enabled': False}

    def fetch_verified(self, provider: DocumentsReadProvider, *, provider_item_ref: str,
                       provider_version_ref: str) -> dict:
        decision = self._certify(provider)
        item = self.registry.get_item_by_provider_ref(decision.provider_id, provider_item_ref)
        if item is None or item.kind != 'file':
            raise DocumentsReadIntegrationError('registered file item not found')
        version_id = self.registry._stable_id('ver', item.item_id, provider_version_ref)
        version = self.registry.get_version(version_id)
        if version is None:
            raise DocumentsReadIntegrationError('registered file version not found')
        fetched = provider.fetch_content(provider_item_ref, provider_version_ref)
        if fetched.provider_id != decision.provider_id or fetched.provider_item_ref != provider_item_ref:
            raise DocumentsReadIntegrationError('provider item identity mismatch during fetch')
        if fetched.provider_version_ref != provider_version_ref:
            raise DocumentsReadIntegrationError('provider version identity mismatch during fetch')
        actual_hash = hashlib.sha256(fetched.content).hexdigest()
        if fetched.content_hash and fetched.content_hash != actual_hash:
            raise DocumentsReadIntegrationError('provider content hash mismatch')
        if version.content_hash and version.content_hash != actual_hash:
            raise DocumentsReadIntegrationError('registered version content hash mismatch')
        if version.size_bytes is not None and version.size_bytes != len(fetched.content):
            raise DocumentsReadIntegrationError('registered version size mismatch')
        return {'item': item, 'version': version, 'content': fetched.content,
                'verified_content_hash': actual_hash,
                'external_calls_made': decision.external_calls_made + 1,
                'write_enabled': False, 'delete_enabled': False}

    @staticmethod
    def _verify_provider_identity(provider_id: str, observations: tuple[ProviderItemObservation, ...]) -> None:
        if any(obs.provider_id != provider_id for obs in observations):
            raise DocumentsReadIntegrationError('provider identity mismatch in observations')
