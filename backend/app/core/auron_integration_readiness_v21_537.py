from __future__ import annotations

from app.core.auron_integration_readiness_v21_536 import get_integration_readiness as get_v21_536_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_536_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.537',
        'current_phase': 'B-trading-vertical',
        'current_item': 'B8-reconciliation-canary-certification',
        'completed_gates': tuple(previous['completed_gates']) + (
            'paper-execution-reconciliation',
            'account-state-consistency-proof',
            'canary-certification-threshold',
            'reconciliation-mismatch-fail-closed',
            'live-path-still-disabled',
        ),
        'next_item': 'B9-controlled-multi-account-live-enablement',
        'core_next_gate': 'controlled-multi-account-live',
        'trading_live_execution_enabled': False,
        'external_calls_made': 0,
    }
