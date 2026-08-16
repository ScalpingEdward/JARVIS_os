from __future__ import annotations

from app.core.auron_integration_readiness_v21_530 import get_integration_readiness as get_v21_530_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_530_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.531',
        'current_phase': 'B-trading-vertical',
        'current_item': 'B2-normalized-trading-account-state',
        'completed_gates': tuple(previous['completed_gates']) + (
            'normalized-account-state-schema',
            'persistent-account-state-store',
            'normalized-positions-orders',
            'trading-day-state',
        ),
        'next_item': 'B3-strategy-signal-intake',
        'core_next_gate': 'strategy-signal-intake',
        'trading_live_execution_enabled': False,
        'external_calls_made': 0,
    }
