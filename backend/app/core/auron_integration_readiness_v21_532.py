from __future__ import annotations

from app.core.auron_integration_readiness_v21_531 import get_integration_readiness as get_v21_531_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_531_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.532',
        'current_phase': 'B-trading-vertical',
        'current_item': 'B3-strategy-signal-intake-separated-from-execution',
        'completed_gates': tuple(previous['completed_gates']) + (
            'strategy-signal-intake',
            'signal-validation',
            'signal-idempotency',
            'execution-separation',
        ),
        'next_item': 'B4-pre-trade-risk-engine',
        'core_next_gate': 'pre-trade-risk-engine',
        'trading_live_execution_enabled': False,
        'external_calls_made': 0,
    }
