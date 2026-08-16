from __future__ import annotations

from app.core.auron_integration_readiness_v21_528 import get_integration_readiness as get_v21_528_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_528_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.529',
        'current_phase': 'B-trading-vertical',
        'current_item': 'A6-end-to-end-integration-harness-cutover-certification',
        'completed_gates': tuple(previous['completed_gates']) + (
            'e2e-integration-harness',
            'core-cutover-certification',
        ),
        'core_cutover_state': 'certifiable-via-v21.529-harness',
        'next_item': 'B1-trading-multi-account-registry-and-provider-rule-profiles',
        'core_next_gate': 'trading-account-registry',
        'live_provider_execution_enabled': False,
        'external_calls_made': 0,
    }
