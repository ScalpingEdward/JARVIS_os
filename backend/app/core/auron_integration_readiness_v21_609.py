from __future__ import annotations
from app.core.auron_integration_readiness_v21_608 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,
        'roadmap_version':'v21.609',
        'current_phase':'H-controlled-external-provider-sandbox-integration',
        'current_item':'H1-external-provider-contract-registry-secretless-sandbox-boundary',
        'completed_gates':tuple(previous['completed_gates'])+(
            'external-provider-contract-registry-persistent',
            'external-provider-capability-declarations-bounded',
            'external-provider-credential-reference-opaque-only',
            'external-provider-raw-secrets-forbidden',
            'external-provider-sandbox-only-contracts',
            'external-provider-readonly-contracts-only',
            'external-provider-network-transport-not-authorized',
            'external-provider-production-transport-not-authorized',),
        'next_item':'H2-research-external-readonly-sandbox-adapter',
        'core_next_gate':'research-external-readonly-sandbox-adapter',
        'live_transports_enabled':False,
        'external_provider_network_enabled':False,
        'external_provider_write_enabled':False,
        'trading_execution_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
