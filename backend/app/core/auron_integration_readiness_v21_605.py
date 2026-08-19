from __future__ import annotations
from app.core.auron_integration_readiness_v21_604 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,
        'roadmap_version':'v21.605',
        'current_phase':'G-provider-specific-canary-integration',
        'current_item':'G18-trading-shadow-canary-adapter',
        'completed_gates':tuple(previous['completed_gates'])+(
            'trading-shadow-adapter-implemented',
            'trading-shadow-F2-execution-compatible',
            'trading-shadow-F3-result-reader-compatible',
            'trading-shadow-F3-stop-compatible',
            'trading-plan-evaluation-persistent',
            'trading-order-intent-simulation-persistent',
            'trading-broker-credentials-forbidden',
            'trading-network-calls-zero',
            'trading-live-order-position-mutation-disabled',),
        'next_item':'G19-trading-shadow-end-to-end-certification',
        'core_next_gate':'trading-shadow-end-to-end-certification',
        'live_transports_enabled':False,
        'trading_execution_enabled':False,
        'trading_broker_network_enabled':False,
        'trading_position_mutation_enabled':False,
        'trading_order_cancel_modify_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
