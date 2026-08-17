from __future__ import annotations

from app.core.auron_integration_readiness_v21_562 import get_integration_readiness as get_v21_562_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_562_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.563',
        'current_phase': 'D-research-vertical',
        'current_item': 'D16-research-command-centre-operations',
        'completed_gates': tuple(previous['completed_gates']) + (
            'research-command-centre-read-model',
            'research-query-source-result-visibility',
            'research-evidence-freshness-visibility',
            'research-report-visibility',
            'research-watch-run-reconciliation-visibility',
            'research-watch-kill-switch-control',
            'research-persistent-command-field',
        ),
        'next_item': 'D17-next-vertical-selection',
        'core_next_gate': 'next-vertical-selection',
        'research_vertical_architecture_complete': True,
        'research_unattended_actions_enabled': False,
        'research_downstream_execution_enabled': False,
        'external_calls_made': 0,
    }
