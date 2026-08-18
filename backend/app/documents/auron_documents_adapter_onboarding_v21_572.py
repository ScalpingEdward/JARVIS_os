from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class DocumentsOnboardingError(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentsProviderDescriptor:
    provider_id: str
    display_name: str
    capabilities: tuple[str, ...]
    permission_scopes: tuple[str, ...]
    supports_read: bool
    supports_metadata: bool
    supports_content_fetch: bool
    supports_version_identity: bool
    supports_write: bool = False
    supports_delete: bool = False


@dataclass(frozen=True)
class DocumentsProviderHealth:
    provider_id: str
    reachable: bool
    authenticated: bool
    identity_verified: bool
    read_scope_verified: bool
    metadata_available: bool
    observed_at: str
    external_calls_made: int = 0


@dataclass(frozen=True)
class DocumentsOnboardingDecision:
    provider_id: str
    accepted: bool
    blockers: tuple[str, ...]
    read_only_certified: bool
    write_enabled: bool
    delete_enabled: bool
    external_calls_made: int


class DocumentsProviderBoundary(Protocol):
    def descriptor(self) -> DocumentsProviderDescriptor: ...
    def read_health(self) -> DocumentsProviderHealth: ...


class DocumentsAdapterOnboardingPolicy:
    """D25 onboarding boundary for governed Files & Documents providers.

    D25 certifies provider identity, read permissions, metadata/content inspection and
    stable version identity only. Mutating file operations are deliberately outside
    this phase and remain disabled even if a provider advertises them.
    """

    REQUIRED_CAPABILITIES = frozenset({'identity', 'health', 'metadata', 'read', 'inspect'})
    REQUIRED_SCOPES = frozenset({'read-only'})

    def evaluate(self, provider: DocumentsProviderBoundary) -> DocumentsOnboardingDecision:
        descriptor = provider.descriptor()
        health = provider.read_health()
        blockers: list[str] = []

        if not descriptor.provider_id.strip():
            blockers.append('provider-id-missing')
        if health.provider_id != descriptor.provider_id:
            blockers.append('provider-identity-mismatch')
        missing_capabilities = self.REQUIRED_CAPABILITIES.difference(descriptor.capabilities)
        if missing_capabilities:
            blockers.append('required-capabilities-missing:' + ','.join(sorted(missing_capabilities)))
        missing_scopes = self.REQUIRED_SCOPES.difference(descriptor.permission_scopes)
        if missing_scopes:
            blockers.append('required-permission-scopes-missing:' + ','.join(sorted(missing_scopes)))
        if not descriptor.supports_read:
            blockers.append('read-not-supported')
        if not descriptor.supports_metadata:
            blockers.append('metadata-not-supported')
        if not descriptor.supports_content_fetch:
            blockers.append('content-fetch-not-supported')
        if not descriptor.supports_version_identity:
            blockers.append('stable-version-identity-not-supported')
        if not health.reachable:
            blockers.append('provider-unreachable')
        if not health.authenticated:
            blockers.append('provider-not-authenticated')
        if not health.identity_verified:
            blockers.append('provider-identity-not-verified')
        if not health.read_scope_verified:
            blockers.append('read-scope-not-verified')
        if not health.metadata_available:
            blockers.append('metadata-unavailable')

        return DocumentsOnboardingDecision(
            provider_id=descriptor.provider_id,
            accepted=not blockers,
            blockers=tuple(blockers),
            read_only_certified=not blockers,
            write_enabled=False,
            delete_enabled=False,
            external_calls_made=health.external_calls_made,
        )

    def require_onboarded(self, decision: DocumentsOnboardingDecision) -> DocumentsOnboardingDecision:
        if not decision.accepted:
            raise DocumentsOnboardingError('documents provider onboarding failed: ' + ';'.join(decision.blockers))
        return decision
