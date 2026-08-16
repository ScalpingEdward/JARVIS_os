from __future__ import annotations

from app.core.auron_integration_readiness_v21_541 import get_integration_readiness as get_v21_541_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_541_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.542',
        'current_phase': 'C-instagram-content-manager',
        'current_item': 'C3-meta-instagram-read-health-adapter',
        'completed_gates': tuple(previous['completed_gates']) + (
            'instagram-provider-read-boundary',
            'instagram-provider-identity-verification',
            'instagram-token-health-observation',
            'instagram-permission-health-observation',
            'instagram-read-only-account-verification',
        ),
        'next_item': 'C4-draft-preview-approval-policy',
        'core_next_gate': 'instagram-draft-preview-approval-policy',
        'instagram_provider_connected': False,
        'instagram_provider_mode': 'read-only-adapter-ready',
        'instagram_publishing_enabled': False,
        'external_calls_made': 0,
    }
