from __future__ import annotations
from app.core.auron_integration_readiness_v21_615 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    p=previous_readiness()
    return {**p,
        'roadmap_version':'v21.616',
        'current_phase':'H-controlled-external-provider-sandbox-integration',
        'current_item':'H8-research-real-provider-activation-readiness-decision',
        'completed_gates':tuple(p['completed_gates'])+(
            'research-real-provider-readiness-requires-clean-h7-certification',
            'research-real-provider-readiness-requires-nonproduction-environment',
            'research-real-provider-readiness-requires-https-endpoint-allowlist',
            'research-real-provider-readiness-requires-safe-credential-provenance',
            'research-real-provider-readiness-requires-readonly-credential-scope',
            'research-real-provider-readiness-requires-operator-approval',
            'research-real-provider-readiness-requires-stop-and-rollback-controls',
            'research-real-provider-readiness-decision-does-not-enable-network',),
        'next_item':'H9-research-real-provider-adapter-contract-design',
        'core_next_gate':'research-real-provider-adapter-contract-design',
        'live_transports_enabled':False,
        'external_provider_network_enabled':False,
        'external_provider_write_enabled':False,
        'external_provider_credential_resolution_enabled':False,
        'real_provider_transport_configured':False,
        'trading_execution_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
