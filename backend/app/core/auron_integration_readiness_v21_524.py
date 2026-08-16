from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

ReadinessState = Literal['blocked', 'foundation-ready', 'integration-ready', 'live-ready']


@dataclass(frozen=True)
class CapabilityReadiness:
    capability: str
    phase: str
    state: ReadinessState
    external_execution_enabled: bool
    required_gates: tuple[str, ...]
    next_gate: str


_CAPABILITIES: dict[str, CapabilityReadiness] = {
    'core': CapabilityReadiness(
        capability='core',
        phase='A-integration-readiness',
        state='foundation-ready',
        external_execution_enabled=False,
        required_gates=('capability-contract', 'persistent-ledger', 'policy-gate', 'command-centre-integration', 'e2e-cutover-certification'),
        next_gate='capability-contract',
    ),
    'trading': CapabilityReadiness(
        capability='trading',
        phase='B-trading-vertical',
        state='blocked',
        external_execution_enabled=False,
        required_gates=('core-cutover', 'account-registry', 'prop-rule-profiles', 'risk-engine', 'execution-adapter', 'reconciliation', 'paper-certification', 'live-canary'),
        next_gate='core-cutover',
    ),
    'instagram-content-manager': CapabilityReadiness(
        capability='instagram-content-manager',
        phase='C-content-vertical',
        state='blocked',
        external_execution_enabled=False,
        required_gates=('core-cutover', 'brand-account-registry', 'content-lifecycle', 'meta-adapter', 'publish-policy-gate', 'scheduler-reconciliation', 'controlled-publish-certification'),
        next_gate='core-cutover',
    ),
}


def get_integration_readiness() -> dict:
    return {
        'roadmap_version': 'v21.524',
        'foundation_checkpoint': 'v21.523-generation-forty-six-complete',
        'current_phase': 'A-integration-readiness-core-cutover',
        'current_item': 'A1-canonical-roadmap-integration-readiness-registry',
        'next_item': 'A2-unified-capability-adapter-contract',
        'capabilities': {name: asdict(value) for name, value in _CAPABILITIES.items()},
        'external_calls_made': 0,
    }


def assert_external_execution_blocked(capability: str) -> None:
    readiness = _CAPABILITIES.get(capability)
    if readiness is None:
        raise KeyError(f'Unknown capability: {capability}')
    if readiness.external_execution_enabled:
        raise RuntimeError(f'{capability} unexpectedly has external execution enabled during integration-readiness phase')
