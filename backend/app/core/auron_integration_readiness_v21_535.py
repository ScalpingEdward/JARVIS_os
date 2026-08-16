from __future__ import annotations

from app.core.auron_integration_readiness_v21_534 import get_integration_readiness as get_v21_534_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_534_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.535',
        'current_phase': 'B-trading-vertical',
        'current_item': 'B6-account-session-news-guards-exposure-loss-kill-switches',
        'completed_gates': tuple(previous['completed_gates']) + (
            'trading-global-kill-switch',
            'trading-per-account-kill-switch',
            'symbol-session-day-guards',
            'restricted-news-guard',
            'exposure-position-loss-guards',
        ),
        'next_item': 'B7-mt5-broker-adapter-read-only-paper',
        'core_next_gate': 'mt5-broker-read-only-paper-adapter',
        'trading_live_execution_enabled': False,
        'external_calls_made': 0,
    }
