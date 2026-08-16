from __future__ import annotations

from app.core.auron_integration_readiness_v21_545 import get_integration_readiness as get_v21_545_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_545_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.546',
        'current_phase': 'C-instagram-content-manager',
        'current_item': 'C7-publish-reconciliation-retries',
        'completed_gates': tuple(previous['completed_gates']) + (
            'content-provider-result-verification',
            'content-publish-reconciliation',
            'content-reconciliation-history',
            'content-bounded-retry-policy',
            'content-retry-exhaustion',
        ),
        'next_item': 'C8-content-command-centre-recurring-automation',
        'core_next_gate': 'instagram-content-command-centre-automation',
        'instagram_provider_connected': False,
        'instagram_publishing_enabled': False,
        'instagram_provider_write_available': False,
        'external_calls_made': 0,
    }
