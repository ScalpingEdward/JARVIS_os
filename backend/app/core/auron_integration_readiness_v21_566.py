from __future__ import annotations

from app.core.auron_integration_readiness_v21_565 import get_integration_readiness as get_v21_565_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_565_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.566',
        'current_phase': 'D-automation-vertical',
        'current_item': 'D19-automation-catalog-read-health-integration',
        'completed_gates': tuple(previous['completed_gates']) + (
            'automation-certified-provider-read-health',
            'automation-normalized-provider-catalog',
            'automation-provider-catalog-identity-verification',
            'automation-catalog-simulation-capability-verification',
            'automation-workflow-action-catalog-validation',
            'automation-read-state-persistence',
            'automation-d19-zero-action-execution',
        ),
        'next_item': 'D20-automation-workflow-policy-approval-boundary',
        'core_next_gate': 'automation-policy-approval-kill-switch-boundary',
        'automation_execution_enabled': False,
        'automation_cross_vertical_execution_enabled': False,
    }
