from __future__ import annotations
from app.core.auron_integration_readiness_v21_607 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,
        'roadmap_version':'v21.608',
        'current_phase':'G-provider-specific-canary-integration',
        'current_item':'G21-provider-expansion-promotion-decision',
        'completed_gates':tuple(previous['completed_gates'])+(
            'cross-provider-canary-evidence-aggregation',
            'provider-expansion-requires-all-canary-health-certification',
            'provider-expansion-duplicate-evidence-fail-closed',
            'provider-expansion-unsafe-capability-fail-closed',
            'research-readonly-sandbox-design-selected',
            'promotion-scope-separated-from-live-capability',
            'live-transport-provider-write-production-remain-disabled',
            'live-trading-explicitly-ineligible-after-shadow-certification'),
        'next_item':'H1-external-provider-contract-registry-secretless-sandbox-boundary',
        'core_next_gate':'external-provider-contract-registry-secretless-sandbox-boundary',
        'live_transports_enabled':False,
        'research_network_transport_enabled':False,
        'trading_execution_enabled':False,
        'trading_broker_network_enabled':False,
        'trading_position_mutation_enabled':False,
        'provider_writes_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
