from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

CommunicationMode = Literal['simulation', 'read-only', 'live']
CommunicationCapability = Literal['identity', 'health', 'read', 'draft', 'send', 'reply']


class CommunicationsOnboardingError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommunicationsProviderDescriptor:
    provider_id: str
    display_name: str
    capabilities: tuple[CommunicationCapability, ...]
    supported_modes: tuple[CommunicationMode, ...]
    requires_operator_approval: bool = True
    supports_idempotency: bool = False
    supports_reconciliation: bool = False


@dataclass(frozen=True)
class CommunicationsProviderHealth:
    provider_id: str
    reachable: bool
    authenticated: bool
    identity_verified: bool
    permissions_verified: bool
    observed_at: str
    external_calls_made: int = 0


@dataclass(frozen=True)
class CommunicationsOnboardingDecision:
    provider_id: str
    accepted: bool
    blockers: tuple[str, ...]
    allowed_mode: CommunicationMode
    outbound_execution_enabled: bool
    external_calls_made: int = 0


class CommunicationsProviderBoundary(Protocol):
    """D1 provider contract only. No outbound send implementation is supplied here."""

    def descriptor(self) -> CommunicationsProviderDescriptor: ...

    def read_health(self) -> CommunicationsProviderHealth: ...


class DisabledCommunicationsProviderBoundary:
    def __init__(self, provider_id: str = 'disabled') -> None:
        self.provider_id = provider_id

    def descriptor(self) -> CommunicationsProviderDescriptor:
        return CommunicationsProviderDescriptor(
            provider_id=self.provider_id,
            display_name='Disabled communications provider',
            capabilities=('identity', 'health'),
            supported_modes=('simulation',),
            requires_operator_approval=True,
            supports_idempotency=False,
            supports_reconciliation=False,
        )

    def read_health(self) -> CommunicationsProviderHealth:
        raise CommunicationsOnboardingError('communications provider boundary is disabled')


class CommunicationsAdapterOnboardingPolicy:
    """Selects and certifies communications adapters before vertical state/execution exists.

    D1 deliberately stops at the onboarding contract. A provider is never granted live
    outbound execution merely because health/identity checks pass.
    """

    REQUIRED_CAPABILITIES = {'identity', 'health', 'read', 'draft'}

    def evaluate(self, provider: CommunicationsProviderBoundary) -> CommunicationsOnboardingDecision:
        descriptor = provider.descriptor()
        blockers: list[str] = []

        if not descriptor.provider_id.strip():
            blockers.append('provider-id-missing')
        if not self.REQUIRED_CAPABILITIES.issubset(set(descriptor.capabilities)):
            blockers.append('required-capabilities-missing')
        if 'simulation' not in descriptor.supported_modes:
            blockers.append('simulation-mode-required')
        if not descriptor.requires_operator_approval:
            blockers.append('operator-approval-must-be-required')

        try:
            health = provider.read_health()
        except Exception:
            health = None
            blockers.append('provider-health-unavailable')

        external_calls = health.external_calls_made if health else 0
        if health is not None:
            if health.provider_id != descriptor.provider_id:
                blockers.append('provider-identity-mismatch')
            if not health.reachable:
                blockers.append('provider-unreachable')
            if not health.authenticated:
                blockers.append('provider-not-authenticated')
            if not health.identity_verified:
                blockers.append('provider-identity-unverified')
            if not health.permissions_verified:
                blockers.append('provider-permissions-unverified')

        return CommunicationsOnboardingDecision(
            provider_id=descriptor.provider_id,
            accepted=not blockers,
            blockers=tuple(dict.fromkeys(blockers)),
            allowed_mode='read-only' if not blockers and 'read-only' in descriptor.supported_modes else 'simulation',
            outbound_execution_enabled=False,
            external_calls_made=external_calls,
        )

    @staticmethod
    def require_onboarded(decision: CommunicationsOnboardingDecision) -> CommunicationsOnboardingDecision:
        if not decision.accepted:
            raise CommunicationsOnboardingError('communications provider is not onboarding-certified')
        if decision.outbound_execution_enabled:
            raise CommunicationsOnboardingError('D1 cannot enable outbound communications execution')
        return decision
