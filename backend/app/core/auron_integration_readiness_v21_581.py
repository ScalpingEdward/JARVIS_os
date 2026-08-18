from __future__ import annotations
from app.core.auron_integration_readiness_v21_580 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous = previous_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.581',
        'current_phase': 'E-cross-vertical-integration-certification',
        'current_item': 'E2-cross-vertical-deterministic-simulation-harness',
        'completed_gates': tuple(previous['completed_gates']) + (
            'cross-vertical-deterministic-simulation-harness',
            'cross-vertical-governed-boundary-only-handoffs',
            'cross-vertical-provider-bypass-rejected',
            'cross-vertical-simulation-idempotency',
            'cross-vertical-zero-provider-writes',
            'cross-vertical-zero-live-actions',
        ),
        'next_item': 'E3-cross-vertical-reconciliation-observability-certification',
        'core_next_gate': 'cross-vertical-reconciliation-observability-certification',
        'live_transports_enabled': False,
        'cross_vertical_direct_provider_bypass_allowed': False,
    }
