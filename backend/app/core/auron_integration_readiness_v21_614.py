from __future__ import annotations
from app.core.auron_integration_readiness_v21_613 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    p=previous_readiness()
    return {**p,
        'roadmap_version':'v21.614',
        'current_phase':'H-controlled-external-provider-sandbox-integration',
        'current_item':'H6-research-readonly-network-transport-boundary',
        'completed_gates':tuple(p['completed_gates'])+(
            'research-network-boundary-requires-positive-h5-decision',
            'research-network-boundary-explicit-separate-activation',
            'research-network-boundary-credential-resolution-isolated',
            'research-network-boundary-get-only-interface',
            'research-network-boundary-https-only',
            'research-network-boundary-hard-request-budget',
            'research-network-boundary-timeout-bounded',
            'research-network-boundary-kill-switch-stop',
            'research-network-boundary-provider-write-disabled',
            'research-network-boundary-no-concrete-provider-client',),
        'next_item':'H7-research-readonly-network-boundary-e2e-certification',
        'core_next_gate':'research-readonly-network-boundary-e2e-certification',
        'live_transports_enabled':False,
        'external_provider_network_enabled':False,
        'external_provider_write_enabled':False,
        'external_provider_credential_resolution_enabled':False,
        'trading_execution_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
