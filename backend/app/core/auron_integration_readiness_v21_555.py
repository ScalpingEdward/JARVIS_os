from __future__ import annotations

from app.core.auron_integration_readiness_v21_554 import get_integration_readiness as get_v21_554_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_554_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.555',
        'current_phase': 'D-communications-vertical',
        'current_item': 'D8-communications-command-centre-operations',
        'completed_gates': tuple(previous['completed_gates']) + (
            'communications-command-centre-read-model',
            'communications-inbox-conversation-visibility',
            'communications-approval-simulation-execution-visibility',
            'communications-reconciliation-alert-visibility',
            'communications-kill-switch-control',
            'communications-persistent-command-field',
        ),
        'next_item': 'D9-next-vertical-selection',
        'core_next_gate': 'next-vertical-selection',
        'communications_vertical_architecture_complete': True,
        'communications_outbound_enabled': False,
        'communications_provider_write_available': False,
        'external_calls_made': 0,
    }
