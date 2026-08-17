from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

ResearchMode = Literal['simulation', 'read-only', 'live']
ResearchCapability = Literal['search', 'fetch', 'source-metadata', 'citations', 'snapshot']


class ResearchOnboardingError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchProviderDescriptor:
    provider_id: str
    display_name: str
    capabilities: tuple[ResearchCapability, ...]
    supported_modes: tuple[ResearchMode, ...]
    supports_source_attribution: bool
    supports_stable_source_ids: bool
    supports_snapshotting: bool


@dataclass(frozen=True)
class ResearchProviderHealth:
    provider_id: str
    reachable: bool
    authenticated: bool
    source_metadata_available: bool
    observed_at: str
    external_calls_made: int = 0


@dataclass(frozen=True)
class ResearchOnboardingDecision:
    provider_id: str
    accepted: bool
    blockers: tuple[str, ...]
    allowed_mode: ResearchMode
    unattended_action_enabled: bool
    external_calls_made: int = 0


class ResearchProviderBoundary(Protocol):
    def descriptor(self) -> ResearchProviderDescriptor: ...
    def read_health(self) -> ResearchProviderHealth: ...


class DisabledResearchProviderBoundary:
    def __init__(self, provider_id: str = 'disabled-research') -> None:
        self.provider_id = provider_id

    def descriptor(self) -> ResearchProviderDescriptor:
        return ResearchProviderDescriptor(
            provider_id=self.provider_id,
            display_name='Disabled research provider',
            capabilities=('source-metadata',),
            supported_modes=('simulation',),
            supports_source_attribution=False,
            supports_stable_source_ids=False,
            supports_snapshotting=False,
        )

    def read_health(self) -> ResearchProviderHealth:
        raise ResearchOnboardingError('research provider boundary is disabled')


class ResearchAdapterOnboardingPolicy:
    """D9 provider contract for governed research/intelligence operations.

    Research is selected as the second Phase-D vertical. D9 only certifies provider
    structure and health. No autonomous actions, publishing, messaging or trading
    execution can be triggered from this layer.
    """

    REQUIRED_CAPABILITIES = {'search', 'fetch', 'source-metadata', 'citations'}

    def evaluate(self, provider: ResearchProviderBoundary) -> ResearchOnboardingDecision:
        descriptor = provider.descriptor()
        blockers: list[str] = []

        if not descriptor.provider_id.strip():
            blockers.append('provider-id-missing')
        if not self.REQUIRED_CAPABILITIES.issubset(set(descriptor.capabilities)):
            blockers.append('required-capabilities-missing')
        if 'simulation' not in descriptor.supported_modes:
            blockers.append('simulation-mode-required')
        if not descriptor.supports_source_attribution:
            blockers.append('source-attribution-required')
        if not descriptor.supports_stable_source_ids:
            blockers.append('stable-source-ids-required')

        try:
            health = provider.read_health()
        except Exception:
            health = None
            blockers.append('provider-health-unavailable')

        calls = health.external_calls_made if health else 0
        if health is not None:
            if health.provider_id != descriptor.provider_id:
                blockers.append('provider-identity-mismatch')
            if not health.reachable:
                blockers.append('provider-unreachable')
            if not health.authenticated:
                blockers.append('provider-not-authenticated')
            if not health.source_metadata_available:
                blockers.append('source-metadata-unavailable')

        return ResearchOnboardingDecision(
            provider_id=descriptor.provider_id,
            accepted=not blockers,
            blockers=tuple(dict.fromkeys(blockers)),
            allowed_mode='read-only' if not blockers and 'read-only' in descriptor.supported_modes else 'simulation',
            unattended_action_enabled=False,
            external_calls_made=calls,
        )

    @staticmethod
    def require_onboarded(decision: ResearchOnboardingDecision) -> ResearchOnboardingDecision:
        if not decision.accepted:
            raise ResearchOnboardingError('research provider is not onboarding-certified')
        if decision.unattended_action_enabled:
            raise ResearchOnboardingError('D9 cannot enable unattended actions')
        return decision
