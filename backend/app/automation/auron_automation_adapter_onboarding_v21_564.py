from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

AutomationMode = Literal['simulation', 'read-only', 'controlled-live']
AutomationCapability = Literal[
    'identity', 'health', 'catalog', 'inspect', 'simulate',
    'schedule', 'execute', 'cancel', 'result-read', 'idempotency',
]


class AutomationOnboardingError(RuntimeError):
    pass


@dataclass(frozen=True)
class AutomationProviderDescriptor:
    provider_id: str
    display_name: str
    capabilities: tuple[AutomationCapability, ...]
    supported_modes: tuple[AutomationMode, ...]
    requires_operator_approval: bool = True
    supports_idempotency: bool = False
    supports_cancellation: bool = False
    supports_result_reconciliation: bool = False
    supports_scoped_credentials: bool = False


@dataclass(frozen=True)
class AutomationProviderHealth:
    provider_id: str
    reachable: bool
    authenticated: bool
    identity_verified: bool
    catalog_available: bool
    permissions_scoped: bool
    observed_at: str
    external_calls_made: int = 0


@dataclass(frozen=True)
class AutomationOnboardingDecision:
    provider_id: str
    accepted: bool
    blockers: tuple[str, ...]
    allowed_mode: AutomationMode
    execution_enabled: bool
    external_calls_made: int = 0


class AutomationProviderBoundary(Protocol):
    """D17 onboarding contract only; no workflow execution method is exposed here."""

    def descriptor(self) -> AutomationProviderDescriptor: ...

    def read_health(self) -> AutomationProviderHealth: ...


class DisabledAutomationProviderBoundary:
    def __init__(self, provider_id: str = 'disabled') -> None:
        self.provider_id = provider_id

    def descriptor(self) -> AutomationProviderDescriptor:
        return AutomationProviderDescriptor(
            provider_id=self.provider_id,
            display_name='Disabled automation provider',
            capabilities=('identity', 'health'),
            supported_modes=('simulation',),
            requires_operator_approval=True,
            supports_idempotency=False,
            supports_cancellation=False,
            supports_result_reconciliation=False,
            supports_scoped_credentials=False,
        )

    def read_health(self) -> AutomationProviderHealth:
        raise AutomationOnboardingError('automation provider boundary is disabled')


class AutomationAdapterOnboardingPolicy:
    """D17 provider certification before workflow execution exists.

    Automation can cross vertical boundaries, so a provider must prove simulation,
    inspectability, scoped permissions, idempotency and result reconciliation before
    later layers may expose controlled execution.
    """

    REQUIRED_CAPABILITIES = {'identity', 'health', 'catalog', 'inspect', 'simulate'}

    def evaluate(self, provider: AutomationProviderBoundary) -> AutomationOnboardingDecision:
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
        if not descriptor.supports_idempotency:
            blockers.append('idempotency-support-required')
        if not descriptor.supports_result_reconciliation:
            blockers.append('result-reconciliation-required')
        if not descriptor.supports_scoped_credentials:
            blockers.append('scoped-credentials-required')

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
            if not health.identity_verified:
                blockers.append('provider-identity-unverified')
            if not health.catalog_available:
                blockers.append('provider-catalog-unavailable')
            if not health.permissions_scoped:
                blockers.append('provider-permissions-not-scoped')

        return AutomationOnboardingDecision(
            provider_id=descriptor.provider_id,
            accepted=not blockers,
            blockers=tuple(dict.fromkeys(blockers)),
            allowed_mode='read-only' if not blockers and 'read-only' in descriptor.supported_modes else 'simulation',
            execution_enabled=False,
            external_calls_made=calls,
        )

    @staticmethod
    def require_onboarded(decision: AutomationOnboardingDecision) -> AutomationOnboardingDecision:
        if not decision.accepted:
            raise AutomationOnboardingError('automation provider is not onboarding-certified')
        if decision.execution_enabled:
            raise AutomationOnboardingError('D17 cannot enable automation execution')
        return decision
