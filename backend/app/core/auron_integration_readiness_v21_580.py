from __future__ import annotations

from app.core.auron_integration_readiness_v21_579 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous = previous_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.580',
        'current_phase': 'E-cross-vertical-integration',
        'current_item': 'E1-cross-vertical-integration-certification',
        'completed_gates': tuple(previous['completed_gates']) + (
            'cross-vertical-required-six-vertical-manifest',
            'cross-vertical-command-centre-certification',
            'cross-vertical-persistent-state-certification',
            'cross-vertical-policy-simulation-execution-boundary-certification',
            'cross-vertical-reconciliation-certification',
            'cross-vertical-kill-disable-control-certification',
            'cross-vertical-command-direct-execution-prohibited',
            'cross-vertical-live-default-off-certification',
            'cross-vertical-direct-provider-bypass-prohibited',
        ),
        'next_item': 'E2-cross-vertical-end-to-end-simulation-harness',
        'core_next_gate': 'cross-vertical-end-to-end-simulation-harness',
        'live_transports_enabled': False,
        'cross_vertical_direct_provider_bypass_allowed': False,
    }
