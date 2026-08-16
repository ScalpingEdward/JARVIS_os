from __future__ import annotations

from app.core.auron_command_centre_v21_528 import build_default_command_centre
from app.core.auron_integration_readiness_v21_527 import get_integration_readiness as get_v21_527_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_527_readiness()
    centre = build_default_command_centre().snapshot()
    return {
        **previous,
        'roadmap_version': 'v21.528',
        'current_item': 'A5-command-centre-real-backend-state-actions-errors-approvals-audit',
        'completed_gates': tuple(previous['completed_gates']) + (
            'command-centre-integration',
            'command-input-preserved',
            'approval-workflow-visible',
            'audit-timeline-visible',
            'backend-state-visible',
        ),
        'next_item': 'A6-end-to-end-integration-harness-cutover-certification',
        'core_next_gate': 'e2e-cutover-certification',
        'command_centre': {
            'command_input_available': centre['command_input_available'],
            'command_execution_enabled': centre['command_execution_enabled'],
            'pending_approvals_count': len(centre['pending_approvals']),
            'external_calls_made': 0,
        },
        'external_calls_made': 0,
    }
