from __future__ import annotations

from app.core.auron_integration_readiness_v21_553 import get_integration_readiness as get_v21_553_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_553_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.554',
        'current_phase': 'D-communications-vertical',
        'current_item': 'D7-communications-reconciliation-retries',
        'completed_gates': tuple(previous['completed_gates']) + (
            'communications-provider-result-verification',
            'communications-provider-ref-verification',
            'communications-provider-channel-verification',
            'communications-idempotency-key-verification',
            'communications-bounded-retry-policy',
            'communications-reconciliation-history',
            'communications-no-blind-resend',
        ),
        'next_item': 'D8-communications-command-centre-operations',
        'core_next_gate': 'communications-command-centre-operations',
        'communications_outbound_enabled': False,
        'communications_provider_write_available': False,
        'external_calls_made': 0,
    }
