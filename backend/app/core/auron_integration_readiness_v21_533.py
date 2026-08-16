from __future__ import annotations

from app.core.auron_integration_readiness_v21_532 import get_integration_readiness as get_v21_532_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_532_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.533',
        'current_phase': 'B-trading-vertical',
        'current_item': 'B4-pre-trade-risk-engine',
        'completed_gates': tuple(previous['completed_gates']) + (
            'pre-trade-risk-engine',
            'account-specific-risk-headroom',
            'daily-max-drawdown-gating',
            'fail-closed-risk-decision',
        ),
        'next_item': 'B5-multi-account-allocation-copy-engine',
        'core_next_gate': 'multi-account-allocation',
        'trading_live_execution_enabled': False,
        'external_calls_made': 0,
    }
