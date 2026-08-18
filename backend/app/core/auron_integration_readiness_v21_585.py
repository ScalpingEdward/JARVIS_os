from __future__ import annotations

from app.core.auron_integration_readiness_v21_584 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous = previous_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.585',
        'current_phase': 'F-controlled-provider-canary-program',
        'current_item': 'F2-controlled-canary-execution-boundary',
        'completed_gates': tuple(previous['completed_gates']) + (
            'canary-F1-artifact-required',
            'canary-adapter-separated-execution-boundary',
            'canary-hard-action-budget',
            'canary-kill-switch-recheck-per-action',
            'canary-reconciliation-stop-recheck-per-action',
            'canary-deterministic-idempotency-key',
            'canary-persistent-execution-state',
            'canary-default-transport-disabled',
        ),
        'next_item': 'F3-canary-result-reconciliation-stop-enforcement',
        'core_next_gate': 'canary-result-reconciliation-stop-enforcement',
        'live_transports_enabled': False,
        'production_canary_auto_activation_enabled': False,
        'cross_vertical_direct_provider_bypass_allowed': False,
    }
