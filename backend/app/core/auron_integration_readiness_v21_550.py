from __future__ import annotations

from app.core.auron_integration_readiness_v21_549 import get_integration_readiness as get_v21_549_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_549_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.550',
        'current_phase': 'D-communications-vertical',
        'current_item': 'D3-communications-read-health-sync',
        'completed_gates': tuple(previous['completed_gates']) + (
            'communications-read-only-provider-sync',
            'communications-provider-identity-check',
            'communications-normalized-conversation-sync',
            'communications-normalized-message-sync',
            'communications-read-sync-idempotency',
        ),
        'next_item': 'D4-communications-policy-approval-boundary',
        'core_next_gate': 'communications-policy-approval',
        'communications_provider_connected': False,
        'communications_outbound_enabled': False,
        'external_calls_made': 0,
    }
