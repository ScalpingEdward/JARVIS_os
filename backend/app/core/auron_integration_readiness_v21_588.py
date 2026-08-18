from __future__ import annotations

from app.core.auron_integration_readiness_v21_587 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous = previous_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.588',
        'current_phase': 'G-provider-specific-canary-integration',
        'current_item': 'G1-research-readonly-canary-adapter-integration',
        'completed_gates': tuple(previous['completed_gates']) + (
            'provider-specific-canary-adapter-selected',
            'research-selected-as-first-canary-vertical',
            'research-readonly-action-contract',
            'research-f2-execution-transport-compatible',
            'research-f3-result-reader-compatible',
            'research-f3-stop-boundary-compatible',
            'research-local-persistent-canary-state',
            'research-zero-network-provider-writes',
            'research-production-transport-disabled',
        ),
        'next_item': 'G2-research-canary-end-to-end-certification-harness',
        'core_next_gate': 'research-provider-specific-canary-e2e-certification',
        'live_transports_enabled': False,
        'production_canary_auto_activation_enabled': False,
        'cross_vertical_direct_provider_bypass_allowed': False,
    }
