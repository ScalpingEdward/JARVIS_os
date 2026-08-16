from __future__ import annotations

from app.core.auron_integration_readiness_v21_548 import get_integration_readiness as get_v21_548_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_548_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.549',
        'current_phase': 'D-communications-vertical',
        'current_item': 'D2-communications-registry-state-model',
        'completed_gates': tuple(previous['completed_gates']) + (
            'communications-account-registry',
            'communications-channel-registry',
            'communications-conversation-state',
            'communications-message-state',
            'communications-message-integrity-idempotency',
            'communications-persistent-normalized-state',
        ),
        'next_item': 'D3-communications-read-health-integration',
        'core_next_gate': 'communications-read-health-integration',
        'communications_provider_connected': False,
        'communications_outbound_enabled': False,
        'external_calls_made': 0,
    }
