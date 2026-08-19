from __future__ import annotations
from app.core.auron_integration_readiness_v21_603 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,
        'roadmap_version':'v21.604',
        'current_phase':'G-provider-specific-canary-integration',
        'current_item':'G17-trading-shadow-only-canary-selection',
        'completed_gates':tuple(previous['completed_gates'])+(
            'trading-shadow-only-candidate-selected',
            'trading-live-provider-ineligible',
            'trading-broker-network-disabled',
            'trading-live-order-placement-disabled',
            'trading-position-mutation-disabled',
            'trading-shadow-actions-bounded-to-analysis-simulation',),
        'next_item':'G18-trading-shadow-canary-adapter',
        'core_next_gate':'trading-shadow-canary-adapter',
        'live_transports_enabled':False,
        'trading_execution_enabled':False,
        'trading_broker_network_enabled':False,
        'trading_position_mutation_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
