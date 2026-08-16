from __future__ import annotations

from app.core.auron_integration_readiness_v21_525 import get_integration_readiness as get_v21_525_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_525_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.526',
        'current_item': 'A3-persistent-execution-audit-ledger-idempotency-reconciliation',
        'completed_gates': (
            'canonical-roadmap',
            'integration-readiness-registry',
            'capability-contract',
            'persistent-ledger',
            'idempotency',
            'reconciliation-primitives',
        ),
        'next_item': 'A4-central-policy-gate-approval-environment-kill-switch-scopes',
        'core_next_gate': 'policy-gate',
        'persistent_state': True,
        'external_calls_made': 0,
    }
