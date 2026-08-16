from __future__ import annotations

from app.core.auron_integration_readiness_v21_543 import get_integration_readiness as get_v21_543_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_543_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.544',
        'current_phase': 'C-instagram-content-manager',
        'current_item': 'C5-scheduler-dry-run',
        'completed_gates': tuple(previous['completed_gates']) + (
            'content-deterministic-schedule-plan',
            'content-current-approval-required',
            'content-revision-bound-dry-run',
            'content-due-queue',
            'content-pre-execution-revalidation',
        ),
        'next_item': 'C6-controlled-meta-publish-boundary',
        'core_next_gate': 'instagram-controlled-provider-write-boundary',
        'instagram_provider_connected': False,
        'instagram_publishing_enabled': False,
        'instagram_provider_write_available': False,
        'external_calls_made': 0,
    }
