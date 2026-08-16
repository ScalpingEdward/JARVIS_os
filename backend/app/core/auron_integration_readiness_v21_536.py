from __future__ import annotations

from app.core.auron_integration_readiness_v21_535 import get_integration_readiness as get_v21_535_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_535_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.536',
        'current_phase': 'B-trading-vertical',
        'current_item': 'B7-mt5-broker-adapter-read-only-paper',
        'completed_gates': tuple(previous['completed_gates']) + (
            'broker-read-only-adapter-contract',
            'normalized-provider-account-sync',
            'risk-gated-paper-execution',
            'paper-execution-idempotency',
            'live-order-method-absent',
        ),
        'next_item': 'B8-reconciliation-canary-certification',
        'core_next_gate': 'trading-reconciliation-canary-certification',
        'trading_live_execution_enabled': False,
        'external_calls_made': 0,
    }
