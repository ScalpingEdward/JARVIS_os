from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Protocol, runtime_checkable

ExecutionMode = Literal['simulation', 'live']
HealthState = Literal['unknown', 'healthy', 'degraded', 'failed']
ReadinessState = Literal['blocked', 'integration-ready', 'live-ready']
Permission = Literal['read', 'simulate', 'external.execute']


@dataclass(frozen=True)
class CapabilityDescriptor:
    capability: str
    provider: str
    adapter_version: str
    supported_modes: tuple[ExecutionMode, ...]
    permissions: tuple[Permission, ...]


@dataclass(frozen=True)
class AdapterHealth:
    state: HealthState
    detail: str
    checked_at: str | None = None


@dataclass(frozen=True)
class AdapterReadiness:
    state: ReadinessState
    blockers: tuple[str, ...]
    external_execution_enabled: bool = False


@dataclass(frozen=True)
class ExecutionContext:
    mode: ExecutionMode
    request_id: str
    capability: str
    operator_approved: bool = False
    external_execution_allowed: bool = False


@dataclass(frozen=True)
class ExecutionResult:
    request_id: str
    capability: str
    mode: ExecutionMode
    status: Literal['simulated', 'executed', 'blocked', 'failed']
    external_calls_made: int
    provider_reference: str | None = None
    detail: str = ''


class CapabilityContractError(RuntimeError):
    pass


@runtime_checkable
class CapabilityAdapter(Protocol):
    def descriptor(self) -> CapabilityDescriptor: ...
    def health(self) -> AdapterHealth: ...
    def readiness(self) -> AdapterReadiness: ...
    def execute(self, context: ExecutionContext, payload: dict[str, Any]) -> ExecutionResult: ...


def validate_adapter_contract(adapter: CapabilityAdapter) -> dict[str, Any]:
    if not isinstance(adapter, CapabilityAdapter):
        raise CapabilityContractError('Adapter does not implement the required capability contract')

    descriptor = adapter.descriptor()
    readiness = adapter.readiness()
    health = adapter.health()

    if not descriptor.capability.strip() or not descriptor.provider.strip():
        raise CapabilityContractError('Capability and provider are required')
    if 'simulation' not in descriptor.supported_modes:
        raise CapabilityContractError('Every adapter must support simulation mode')
    if readiness.external_execution_enabled and readiness.state != 'live-ready':
        raise CapabilityContractError('External execution cannot be enabled before live-ready state')
    if readiness.external_execution_enabled and 'live' not in descriptor.supported_modes:
        raise CapabilityContractError('Live execution enabled on an adapter without live-mode support')
    if readiness.external_execution_enabled and 'external.execute' not in descriptor.permissions:
        raise CapabilityContractError('Live-ready adapter lacks external.execute permission')

    return {
        'descriptor': asdict(descriptor),
        'health': asdict(health),
        'readiness': asdict(readiness),
        'contract_valid': True,
        'external_calls_made': 0,
    }


def guard_execution(adapter: CapabilityAdapter, context: ExecutionContext) -> None:
    descriptor = adapter.descriptor()
    readiness = adapter.readiness()

    if context.capability != descriptor.capability:
        raise CapabilityContractError('Execution context capability does not match adapter capability')
    if context.mode not in descriptor.supported_modes:
        raise CapabilityContractError(f'Execution mode {context.mode} is not supported')

    if context.mode == 'simulation':
        if 'simulate' not in descriptor.permissions:
            raise CapabilityContractError('Adapter lacks simulate permission')
        return

    if readiness.state != 'live-ready':
        raise CapabilityContractError('Live execution blocked: adapter is not live-ready')
    if not readiness.external_execution_enabled:
        raise CapabilityContractError('Live execution blocked: external execution is disabled')
    if 'external.execute' not in descriptor.permissions:
        raise CapabilityContractError('Live execution blocked: external.execute permission missing')
    if not context.operator_approved:
        raise CapabilityContractError('Live execution blocked: operator approval missing')
    if not context.external_execution_allowed:
        raise CapabilityContractError('Live execution blocked: policy has not allowed external execution')


def assert_result_accounting(result: ExecutionResult) -> None:
    if result.external_calls_made < 0:
        raise CapabilityContractError('external_calls_made cannot be negative')
    if result.mode == 'simulation' and result.external_calls_made != 0:
        raise CapabilityContractError('Simulation mode must not make external calls')
    if result.status == 'simulated' and result.mode != 'simulation':
        raise CapabilityContractError('Simulated result must use simulation mode')


class ContractOnlyAdapter:
    """Reference adapter used to prove the common contract without any real provider execution."""

    def __init__(self, capability: str, provider: str = 'contract-only') -> None:
        self._descriptor = CapabilityDescriptor(
            capability=capability,
            provider=provider,
            adapter_version='v21.525',
            supported_modes=('simulation',),
            permissions=('read', 'simulate'),
        )

    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def health(self) -> AdapterHealth:
        return AdapterHealth(state='healthy', detail='contract reference adapter; no provider connection')

    def readiness(self) -> AdapterReadiness:
        return AdapterReadiness(
            state='integration-ready',
            blockers=('persistent-ledger', 'policy-gate', 'command-centre-integration', 'e2e-cutover-certification'),
            external_execution_enabled=False,
        )

    def execute(self, context: ExecutionContext, payload: dict[str, Any]) -> ExecutionResult:
        guard_execution(self, context)
        result = ExecutionResult(
            request_id=context.request_id,
            capability=context.capability,
            mode='simulation',
            status='simulated',
            external_calls_made=0,
            detail=f'validated simulation payload keys: {sorted(payload.keys())}',
        )
        assert_result_accounting(result)
        return result
