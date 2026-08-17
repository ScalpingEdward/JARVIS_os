from __future__ import annotations

from app.core.auron_integration_readiness_v21_552 import get_integration_readiness as get_v21_552_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_552_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.553',
        'current_phase': 'D-communications-vertical',
        'current_item': 'D6-communications-controlled-execution',
        'completed_gates': tuple(previous['completed_gates']) + (
            'communications-successful-dry-run-required',
            'communications-current-approval-before-execution',
            'communications-explicit-channel-execution-scope',
            'communications-operator-enablement',
            'communications-execution-kill-switch',
            'communications-idempotent-execution-id',
            'communications-explicit-provider-write-boundary',
        ),
        'next_item': 'D7-communications-reconciliation-retries',
        'core_next_gate': 'communications-provider-result-reconciliation',
        'communications_provider_connected': False,
        'communications_outbound_enabled': False,
        'communications_provider_write_available': False,
        'external_calls_made': 0,
    }
