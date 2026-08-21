from __future__ import annotations
from app.core.auron_integration_readiness_v21_614 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    p=previous_readiness()
    return {**p,
        'roadmap_version':'v21.615',
        'current_phase':'H-controlled-external-provider-sandbox-integration',
        'current_item':'H7-research-readonly-network-boundary-e2e-certification',
        'completed_gates':tuple(p['completed_gates'])+(
            'research-network-e2e-h5-h6-chain-certified-with-fakes',
            'research-network-e2e-explicit-activation-certified',
            'research-network-e2e-request-accounting-certified',
            'research-network-e2e-hard-budget-stop-certified',
            'research-network-e2e-provider-write-zero-certified',
            'research-network-e2e-real-provider-transport-out-of-scope',),
        'next_item':'H8-research-network-provider-activation-readiness-decision',
        'core_next_gate':'research-network-provider-activation-readiness-decision',
        'live_transports_enabled':False,
        'external_provider_network_enabled':False,
        'external_provider_write_enabled':False,
        'external_provider_credential_resolution_enabled':False,
        'real_provider_transport_configured':False,
        'trading_execution_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
