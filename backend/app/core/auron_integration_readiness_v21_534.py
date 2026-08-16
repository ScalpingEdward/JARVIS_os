from __future__ import annotations

from app.core.auron_integration_readiness_v21_533 import get_integration_readiness as get_v21_533_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_533_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.534',
        'current_phase': 'B-trading-vertical',
        'current_item': 'B5-multi-account-allocation-copy-engine',
        'completed_gates': tuple(previous['completed_gates']) + (
            'multi-account-allocation-engine',
            'account-specific-child-intents',
            'risk-derived-lot-sizing',
            'no-blind-lot-copying',
        ),
        'next_item': 'B6-account-session-news-guards-and-kill-switches',
        'core_next_gate': 'trading-guards-kill-switches',
        'trading_live_execution_enabled': False,
        'external_calls_made': 0,
    }
