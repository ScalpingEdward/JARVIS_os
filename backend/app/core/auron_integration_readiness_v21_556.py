from __future__ import annotations

from app.core.auron_integration_readiness_v21_555 import get_integration_readiness as get_v21_555_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_555_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.556',
        'current_phase': 'D-research-vertical',
        'current_item': 'D9-research-provider-adapter-onboarding',
        'completed_gates': tuple(previous['completed_gates']) + (
            'research-vertical-selected',
            'research-provider-contract-defined',
            'research-source-attribution-required',
            'research-stable-source-id-required',
            'research-simulation-first-contract',
            'research-unattended-actions-disabled',
        ),
        'next_item': 'D10-research-source-registry-state-model',
        'core_next_gate': 'research-source-registry-state',
        'research_provider_connected': False,
        'research_unattended_actions_enabled': False,
        'external_calls_made': 0,
    }
