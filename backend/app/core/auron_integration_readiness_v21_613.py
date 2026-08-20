from __future__ import annotations
from app.core.auron_integration_readiness_v21_612 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    p=previous_readiness()
    return {**p,
        'roadmap_version':'v21.613',
        'current_phase':'H-controlled-external-provider-sandbox-integration',
        'current_item':'H5-research-network-transport-authorization-decision',
        'completed_gates':tuple(p['completed_gates'])+(
            'research-network-authorization-decision-persistent',
            'research-network-authorization-requires-h4-operational-readiness',
            'research-network-authorization-requires-operator-approval',
            'research-network-authorization-requires-stop-and-rollback-controls',
            'research-network-authorization-capability-contract-bound',
            'research-network-authorization-credential-reference-state-bound',
            'research-network-authorization-does-not-enable-transport',
            'research-network-authorization-fail-closed',),
        'next_item':'H6-research-readonly-network-transport-boundary',
        'core_next_gate':'research-readonly-network-transport-boundary',
        'live_transports_enabled':False,
        'external_provider_network_enabled':False,
        'external_provider_write_enabled':False,
        'external_provider_credential_resolution_enabled':False,
        'trading_execution_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
