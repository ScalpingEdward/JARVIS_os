from __future__ import annotations

from app.core.auron_integration_readiness_v21_540 import get_integration_readiness as get_v21_540_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_540_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.541',
        'current_phase': 'C-instagram-content-manager',
        'current_item': 'C2-content-lifecycle-version-history',
        'completed_gates': tuple(previous['completed_gates']) + (
            'content-lifecycle-state-machine',
            'immutable-content-revisions',
            'caption-hashtag-asset-creative-metadata',
            'revision-integrity-hashes',
            'calendar-lifecycle-state-sync',
        ),
        'next_item': 'C3-meta-instagram-read-health-adapter',
        'core_next_gate': 'instagram-provider-read-health-adapter',
        'instagram_provider_connected': False,
        'instagram_publishing_enabled': False,
        'external_calls_made': 0,
    }
