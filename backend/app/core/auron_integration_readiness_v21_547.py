from __future__ import annotations

from app.core.auron_integration_readiness_v21_546 import get_integration_readiness as get_v21_546_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_546_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.547',
        'current_phase': 'C-instagram-content-manager',
        'current_item': 'C8-content-command-centre-recurring-automation',
        'completed_gates': tuple(previous['completed_gates']) + (
            'content-command-centre-state',
            'content-command-input-preserved',
            'content-account-alerts',
            'content-recurring-automation-policy',
            'content-automation-explicit-operator-approval',
            'content-automation-no-provider-bypass',
        ),
        'next_item': 'D1-additional-vertical-selection-and-adapter-onboarding',
        'core_next_gate': 'additional-vertical-selection',
        'instagram_content_phase_complete': True,
        'instagram_provider_connected': False,
        'instagram_publishing_enabled': False,
        'instagram_provider_write_available': False,
        'external_calls_made': 0,
    }
