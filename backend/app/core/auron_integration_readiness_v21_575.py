from __future__ import annotations

from app.core.auron_integration_readiness_v21_574 import get_integration_readiness as get_v21_574_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_574_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.575',
        'current_phase': 'D-documents-vertical',
        'current_item': 'D28-documents-provenance-version-access-policy',
        'completed_gates': tuple(previous['completed_gates']) + (
            'documents-registered-provenance-policy',
            'documents-explicit-access-grant-policy',
            'documents-provider-item-scope-policy',
            'documents-current-version-required-for-mutation-simulation',
            'documents-access-revocation',
            'documents-d28-mutation-execution-fail-closed',
        ),
        'next_item': 'D29-documents-deterministic-mutation-simulation',
        'core_next_gate': 'documents-deterministic-mutation-plan-simulation',
        'documents_write_enabled': False,
        'documents_delete_enabled': False,
        'documents_move_enabled': False,
    }
