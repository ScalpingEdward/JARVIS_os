from __future__ import annotations

from app.core.auron_integration_readiness_v21_526 import get_integration_readiness as get_v21_526_readiness
from app.core.auron_policy_gate_v21_527 import CentralPolicyGate


def get_integration_readiness() -> dict:
    previous = get_v21_526_readiness()
    policy = CentralPolicyGate().snapshot()
    return {
        **previous,
        'roadmap_version': 'v21.527',
        'current_item': 'A4-central-policy-gate-approval-environment-kill-switch-scopes',
        'completed_gates': (
            'canonical-roadmap',
            'integration-readiness-registry',
            'capability-contract',
            'persistent-ledger',
            'idempotency',
            'reconciliation-primitives',
            'central-policy-gate',
            'operator-approval-gate',
            'environment-mode-gate',
            'global-kill-switch',
            'capability-kill-switches',
            'capability-scopes',
        ),
        'next_item': 'A5-command-centre-real-backend-state-actions-errors-approvals-audit',
        'core_next_gate': 'command-centre-integration',
        'policy_snapshot': policy,
        'external_calls_made': 0,
    }
