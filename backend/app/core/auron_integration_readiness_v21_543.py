from __future__ import annotations

from app.core.auron_integration_readiness_v21_542 import get_integration_readiness as get_v21_542_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_542_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.543',
        'current_phase': 'C-instagram-content-manager',
        'current_item': 'C4-draft-preview-approval-policy',
        'completed_gates': tuple(previous['completed_gates']) + (
            'content-preview-artifact',
            'preview-revision-integrity-binding',
            'explicit-publish-approval',
            'approval-revision-integrity-binding',
            'provider-read-verification-before-approval',
            'stale-approval-fail-closed',
            'approval-revocation',
        ),
        'next_item': 'C5-scheduler-dry-run',
        'core_next_gate': 'instagram-scheduler-dry-run',
        'instagram_provider_mode': 'read-only-adapter-ready',
        'instagram_publishing_enabled': False,
        'instagram_provider_write_available': False,
        'external_calls_made': 0,
    }
