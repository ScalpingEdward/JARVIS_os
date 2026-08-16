from __future__ import annotations

from app.core.auron_integration_readiness_v21_539 import get_integration_readiness as get_v21_539_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_539_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.540',
        'current_phase': 'C-instagram-content-manager',
        'current_item': 'C1-brand-account-registry-content-calendar',
        'completed_gates': tuple(previous['completed_gates']) + (
            'content-brand-registry',
            'instagram-account-registry',
            'persistent-content-calendar',
            'content-account-brand-integrity',
            'publishing-default-disabled',
        ),
        'next_item': 'C2-content-lifecycle-version-history',
        'core_next_gate': 'instagram-content-lifecycle-version-history',
        'instagram_provider_connected': False,
        'instagram_publishing_enabled': False,
        'external_calls_made': 0,
    }
