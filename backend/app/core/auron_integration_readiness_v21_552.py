from __future__ import annotations

from app.core.auron_integration_readiness_v21_551 import get_integration_readiness as get_v21_551_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_551_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.552',
        'current_phase': 'D-communications-vertical',
        'current_item': 'D5-communications-simulation-dry-run',
        'completed_gates': tuple(previous['completed_gates']) + (
            'communications-deterministic-dry-run-plan',
            'communications-current-approval-revalidation',
            'communications-payload-integrity-revalidation',
            'communications-reply-state-revalidation',
            'communications-zero-write-simulation',
        ),
        'next_item': 'D6-communications-controlled-execution',
        'core_next_gate': 'communications-controlled-provider-write-boundary',
        'communications_provider_connected': False,
        'communications_outbound_enabled': False,
        'communications_provider_write_available': False,
        'external_calls_made': 0,
    }
