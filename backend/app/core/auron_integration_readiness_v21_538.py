from __future__ import annotations

from app.core.auron_integration_readiness_v21_537 import get_integration_readiness as get_v21_537_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_537_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.538',
        'current_phase': 'B-trading-vertical',
        'current_item': 'B9-controlled-live-enablement-architecture',
        'completed_gates': tuple(previous['completed_gates']) + (
            'explicit-live-account-scope',
            'operator-live-approval',
            'canary-certification-required',
            'kill-switch-live-enforcement',
            'explicit-provider-write-boundary',
            'live-idempotency-key',
        ),
        'next_item': 'B10-command-centre-trading-operations',
        'core_next_gate': 'trading-command-centre-operations',
        # Architecture exists, but default provider write boundary remains disabled.
        'trading_live_execution_enabled': False,
        'external_calls_made': 0,
    }
