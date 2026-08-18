from __future__ import annotations

from app.core.auron_integration_readiness_v21_583 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous = previous_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.584',
        'current_phase': 'F-controlled-provider-canary-program',
        'current_item': 'F1-controlled-provider-canary-activation-contract',
        'completed_gates': tuple(previous['completed_gates']) + (
            'canary-E4-decision-binding',
            'canary-single-provider-vertical-binding',
            'canary-explicit-operator-scope-binding',
            'canary-bounded-action-allowance',
            'canary-kill-switch-precondition',
            'canary-reconciliation-stop-preconditions',
            'canary-transport-preactivation-disabled-check',
            'canary-F1-authorization-artifact-only',
        ),
        'next_item': 'F2-controlled-canary-execution-boundary',
        'core_next_gate': 'controlled-canary-execution-boundary',
        'live_transports_enabled': False,
        'production_canary_auto_activation_enabled': False,
        'cross_vertical_direct_provider_bypass_allowed': False,
    }
