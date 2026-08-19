from __future__ import annotations
from app.core.auron_integration_readiness_v21_593 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous = previous_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.594',
        'current_phase': 'G-provider-specific-canary-integration',
        'current_item': 'G7-instagram-draft-preview-end-to-end-certification',
        'completed_gates': tuple(previous['completed_gates']) + (
            'instagram-F1-F2-G6-F3-F4-chain-wired',
            'instagram-provider-specific-identity-bound',
            'instagram-draft-preview-action-e2e-certified',
            'instagram-immediate-result-reconciliation-e2e',
            'instagram-promotion-hold-artifact-e2e',
            'instagram-public-publish-e2e-disabled',
            'instagram-provider-write-e2e-disabled',
            'instagram-network-transport-e2e-disabled',
            'instagram-production-transport-e2e-disabled',
        ),
        'next_item': 'G8-instagram-health-drift-command-centre-certification',
        'core_next_gate': 'instagram-health-drift-command-centre-certification',
        'live_transports_enabled': False,
        'production_canary_auto_activation_enabled': False,
        'cross_vertical_direct_provider_bypass_allowed': False,
    }
