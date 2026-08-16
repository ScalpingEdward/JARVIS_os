from __future__ import annotations

from app.core.auron_integration_readiness_v21_547 import get_integration_readiness as get_v21_547_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_547_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.548',
        'current_phase': 'D-additional-verticals',
        'current_item': 'D1-communications-adapter-onboarding-contract',
        'completed_gates': tuple(previous['completed_gates']) + (
            'communications-vertical-selected',
            'communications-provider-contract-defined',
            'communications-health-identity-contract',
            'communications-simulation-first-contract',
            'communications-outbound-disabled-d1',
        ),
        'next_item': 'D2-communications-registry-state-model',
        'core_next_gate': 'communications-registry-state',
        'communications_provider_connected': False,
        'communications_outbound_enabled': False,
        'external_calls_made': 0,
    }
