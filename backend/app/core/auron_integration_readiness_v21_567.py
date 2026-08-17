from __future__ import annotations

from app.core.auron_integration_readiness_v21_566 import get_integration_readiness as get_v21_566_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_566_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.567',
        'current_phase': 'D-automation-vertical',
        'current_item': 'D20-automation-workflow-policy-approval-boundary',
        'completed_gates': tuple(previous['completed_gates']) + (
            'automation-explicit-operator-approval',
            'automation-provider-scope-policy',
            'automation-target-vertical-scope-policy',
            'automation-workflow-kill-switch-default-on',
            'automation-catalog-revalidation-before-authorization',
            'automation-approval-revocation',
            'automation-d20-live-execution-fail-closed',
        ),
        'next_item': 'D21-automation-deterministic-simulation-dry-run',
        'core_next_gate': 'automation-deterministic-action-plan-simulation',
        'automation_execution_enabled': False,
        'automation_cross_vertical_execution_enabled': False,
    }
