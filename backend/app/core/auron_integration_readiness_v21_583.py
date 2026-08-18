from __future__ import annotations

from app.core.auron_integration_readiness_v21_582 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous = previous_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.583',
        'current_phase': 'E-cross-vertical-integration-certification',
        'current_item': 'E4-production-readiness-canary-gate',
        'completed_gates': tuple(previous['completed_gates']) + (
            'production-readiness-e1-e3-proof-required',
            'production-readiness-provider-health-required',
            'production-readiness-policy-gate-required',
            'production-readiness-kill-switch-required-active-before-canary',
            'production-readiness-idempotency-reconciliation-required',
            'production-readiness-explicit-operator-approval',
            'production-readiness-bounded-canary-scope',
            'production-readiness-transport-disabled-during-certification',
            'production-readiness-rollback-stop-control-required',
            'production-readiness-e4-no-live-enable',
        ),
        'next_item': 'F1-controlled-provider-canary-activation-contract',
        'core_next_gate': 'controlled-provider-canary-activation-contract',
        'phase_e_complete': True,
        'live_transports_enabled': False,
        'cross_vertical_direct_provider_bypass_allowed': False,
        'production_canary_auto_activation_enabled': False,
    }
