from __future__ import annotations

from app.core.auron_integration_readiness_v21_563 import get_integration_readiness as get_v21_563_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_563_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.564',
        'current_phase': 'D-automation-vertical',
        'current_item': 'D17-automation-provider-adapter-onboarding',
        'completed_gates': tuple(previous['completed_gates']) + (
            'automation-vertical-selected',
            'automation-provider-contract-defined',
            'automation-simulation-first-contract',
            'automation-scoped-permissions-required',
            'automation-idempotency-required',
            'automation-result-reconciliation-required',
            'automation-execution-disabled-d17',
        ),
        'next_item': 'D18-automation-workflow-trigger-action-registry',
        'core_next_gate': 'automation-workflow-registry-state',
        'automation_provider_connected': False,
        'automation_execution_enabled': False,
        'automation_cross_vertical_execution_enabled': False,
        'external_calls_made': 0,
    }
