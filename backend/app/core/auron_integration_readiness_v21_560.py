from __future__ import annotations

from app.core.auron_integration_readiness_v21_559 import get_integration_readiness as get_v21_559_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_559_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.560',
        'current_phase': 'D-research-vertical',
        'current_item': 'D13-research-simulation-report-assembly',
        'completed_gates': tuple(previous['completed_gates']) + (
            'research-d12-admissible-evidence-only',
            'research-deterministic-report-assembly',
            'research-explicit-evidence-citations',
            'research-report-hash',
            'research-idempotent-report-id',
            'research-local-simulation-only',
            'research-zero-downstream-execution',
        ),
        'next_item': 'D14-controlled-research-watch-execution',
        'core_next_gate': 'research-controlled-recurring-watch-boundary',
        'research_unattended_actions_enabled': False,
        'research_downstream_execution_enabled': False,
        'external_calls_made': 0,
    }
