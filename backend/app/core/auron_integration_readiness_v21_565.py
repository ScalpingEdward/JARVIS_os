from __future__ import annotations

from app.core.auron_integration_readiness_v21_564 import get_integration_readiness as get_v21_564_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_564_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.565',
        'current_phase': 'D-automation-vertical',
        'current_item': 'D18-automation-workflow-trigger-action-registry',
        'completed_gates': tuple(previous['completed_gates']) + (
            'automation-persistent-workflow-registry',
            'automation-normalized-trigger-registry',
            'automation-normalized-action-registry',
            'automation-provider-neutral-workflow-state',
            'automation-integrity-bound-workflow-definitions',
            'automation-action-ordering',
            'automation-simulation-readiness-state',
            'automation-no-action-execution-d18',
        ),
        'next_item': 'D19-automation-catalog-read-health-integration',
        'core_next_gate': 'automation-certified-catalog-read-health-integration',
        'automation_execution_enabled': False,
        'automation_cross_vertical_execution_enabled': False,
        'external_calls_made': 0,
    }
