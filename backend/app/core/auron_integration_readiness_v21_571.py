from __future__ import annotations

from app.core.auron_integration_readiness_v21_570 import get_integration_readiness as get_v21_570_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_570_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.571',
        'current_phase': 'D-automation-vertical',
        'current_item': 'D24-automation-command-centre-operations',
        'completed_gates': tuple(previous['completed_gates']) + (
            'automation-command-centre-workflow-visibility',
            'automation-command-centre-provider-catalog-visibility',
            'automation-command-centre-approval-policy-visibility',
            'automation-command-centre-simulation-visibility',
            'automation-command-centre-execution-visibility',
            'automation-command-centre-reconciliation-retry-cancellation-visibility',
            'automation-command-centre-governed-kill-controls',
            'automation-persistent-command-field',
            'automation-command-field-recorded-not-executed',
        ),
        'next_item': 'D25-next-vertical-selection-and-adapter-onboarding',
        'core_next_gate': 'next-vertical-selection-and-adapter-contract',
        'automation_vertical_architecture_complete': True,
        'automation_execution_enabled': False,
        'automation_cross_vertical_execution_enabled': False,
        'automation_execution_transport_available': False,
        'external_calls_made': 0,
    }
