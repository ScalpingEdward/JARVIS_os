from __future__ import annotations

from app.core.auron_integration_readiness_v21_557 import get_integration_readiness as get_v21_557_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_557_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.558',
        'current_phase': 'D-research-vertical',
        'current_item': 'D11-research-read-search-fetch-integration',
        'completed_gates': tuple(previous['completed_gates']) + (
            'research-provider-recertification-before-read',
            'research-provider-search-integration',
            'research-provider-fetch-integration',
            'research-search-fetch-identity-verification',
            'research-provider-source-ref-persistence',
            'research-read-results-normalized-into-d10',
            'research-zero-downstream-actions',
        ),
        'next_item': 'D12-research-evidence-provenance-confidence-policy',
        'core_next_gate': 'research-evidence-provenance-confidence-policy',
        'research_unattended_actions_enabled': False,
        'research_downstream_execution_enabled': False,
        'external_calls_made': 0,
    }
