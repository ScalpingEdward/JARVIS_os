from __future__ import annotations

from app.core.auron_integration_readiness_v21_529 import get_integration_readiness as get_v21_529_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_529_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.530',
        'current_phase': 'B-trading-vertical',
        'current_item': 'B1-trading-multi-account-registry-and-provider-rule-profiles',
        'completed_gates': tuple(previous['completed_gates']) + (
            'trading-multi-account-registry',
            'provider-rule-profile-schema',
            'prop-firm-rule-profile-seeds',
        ),
        'next_item': 'B2-normalized-trading-account-state',
        'core_next_gate': 'normalized-account-state',
        'trading_live_execution_enabled': False,
        'external_calls_made': 0,
    }
