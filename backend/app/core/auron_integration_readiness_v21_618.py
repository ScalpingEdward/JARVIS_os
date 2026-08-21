from __future__ import annotations
from app.core.auron_integration_readiness_v21_617 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    p=previous_readiness()
    return {**p,
        'roadmap_version':'v21.618',
        'current_phase':'H-controlled-external-provider-sandbox-integration',
        'current_item':'H10-research-real-provider-adapter-contract-certification',
        'completed_gates':tuple(p['completed_gates'])+(
            'research-real-provider-h8-h9-structural-binding-certified',
            'research-real-provider-endpoint-allowlist-certified',
            'research-real-provider-get-only-certified',
            'research-real-provider-secretref-readonly-certified',
            'research-real-provider-audit-minimum-certified',
            'research-real-provider-raw-material-persistence-forbidden-certified',
            'research-real-provider-design-only-boundary-certified',),
        'next_item':'H11-research-real-provider-adapter-implementation-skeleton',
        'core_next_gate':'research-real-provider-adapter-implementation-skeleton',
        'live_transports_enabled':False,
        'external_provider_network_enabled':False,
        'external_provider_write_enabled':False,
        'external_provider_credential_resolution_enabled':False,
        'real_provider_transport_configured':False,
        'real_provider_adapter_implemented':False,
        'trading_execution_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
