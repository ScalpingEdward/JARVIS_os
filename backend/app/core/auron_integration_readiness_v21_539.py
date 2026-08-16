from __future__ import annotations

from app.core.auron_integration_readiness_v21_538 import get_integration_readiness as get_v21_538_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_538_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.539',
        'current_phase': 'B-trading-vertical',
        'current_item': 'B10-command-centre-trading-operations',
        'completed_gates': tuple(previous['completed_gates']) + (
            'trading-command-centre-account-state',
            'trading-dd-headroom-visibility',
            'trading-canary-visibility',
            'trading-paper-execution-visibility',
            'trading-alert-visibility',
            'trading-kill-control-surface',
            'trading-command-field-preserved',
        ),
        'next_item': 'C1-instagram-brand-account-registry-content-calendar',
        'core_next_gate': 'instagram-content-registry-calendar',
        'trading_live_execution_enabled': False,
        'phase_b_architecture_complete': True,
        'external_calls_made': 0,
    }
