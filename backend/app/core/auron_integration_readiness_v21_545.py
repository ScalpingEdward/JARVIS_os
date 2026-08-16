from __future__ import annotations

from app.core.auron_integration_readiness_v21_544 import get_integration_readiness as get_v21_544_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_544_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.545',
        'current_phase': 'C-instagram-content-manager',
        'current_item': 'C6-controlled-meta-publish-boundary',
        'completed_gates': tuple(previous['completed_gates']) + (
            'content-successful-dry-run-required',
            'content-explicit-publish-scope',
            'content-operator-publish-approval',
            'content-publish-kill-switch',
            'content-explicit-provider-write-boundary',
            'content-idempotent-publish-id',
        ),
        'next_item': 'C7-publish-reconciliation-retries',
        'core_next_gate': 'instagram-publish-reconciliation-retries',
        'instagram_provider_connected': False,
        'instagram_publishing_enabled': False,
        'instagram_provider_write_available': False,
        'external_calls_made': 0,
    }
