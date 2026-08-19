from __future__ import annotations
from app.core.auron_integration_readiness_v21_605 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,'roadmap_version':'v21.606','current_phase':'G-provider-specific-canary-integration',
        'current_item':'G19-trading-shadow-canary-end-to-end-certification',
        'completed_gates':tuple(previous['completed_gates'])+(
            'trading-shadow-F1-F2-G18-F3-F4-chain-wired','trading-shadow-provider-action-identity-bound',
            'trading-shadow-idempotent-execution-reconciliation','trading-shadow-promotion-hold-artifact-e2e',
            'trading-shadow-broker-network-e2e-disabled','trading-shadow-live-orders-e2e-disabled',
            'trading-shadow-position-mutation-e2e-disabled','trading-shadow-zero-external-calls-e2e'),
        'next_item':'G20-trading-shadow-health-drift-command-centre-certification',
        'core_next_gate':'trading-shadow-health-drift-command-centre-certification',
        'live_transports_enabled':False,'trading_execution_enabled':False,'trading_broker_network_enabled':False,
        'trading_position_mutation_enabled':False,'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
