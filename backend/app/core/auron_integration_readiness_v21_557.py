from __future__ import annotations

from app.core.auron_integration_readiness_v21_556 import get_integration_readiness as get_v21_556_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_556_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.557',
        'current_phase': 'D-research-vertical',
        'current_item': 'D10-research-registry-evidence-freshness',
        'completed_gates': tuple(previous['completed_gates']) + (
            'research-persistent-query-registry',
            'research-persistent-source-registry',
            'research-normalized-result-registry',
            'research-stable-source-identities',
            'research-content-integrity-hashes',
            'research-evidence-binding-hashes',
            'research-source-attribution-state',
            'research-freshness-state',
            'research-evidence-history',
        ),
        'next_item': 'D11-research-read-health-integration',
        'core_next_gate': 'research-provider-read-health-integration',
        'research_unattended_actions_enabled': False,
        'research_downstream_execution_enabled': False,
        'external_calls_made': 0,
    }
