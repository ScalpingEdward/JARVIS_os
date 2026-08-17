from __future__ import annotations

from app.core.auron_integration_readiness_v21_550 import get_integration_readiness as get_v21_550_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_550_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.551',
        'current_phase': 'D-communications-vertical',
        'current_item': 'D4-communications-policy-approval-boundary',
        'completed_gates': tuple(previous['completed_gates']) + (
            'communications-outbound-intent-model',
            'communications-reply-conversation-binding',
            'communications-content-hash-approval-binding',
            'communications-approval-revocation',
            'communications-simulation-only-authorization',
        ),
        'next_item': 'D5-communications-simulation-dry-run',
        'core_next_gate': 'communications-simulation-dry-run',
        'communications_provider_connected': False,
        'communications_outbound_enabled': False,
        'external_calls_made': 0,
    }
