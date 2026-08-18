from __future__ import annotations

from app.core.auron_integration_readiness_v21_572 import get_integration_readiness as get_v21_572_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_572_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.573',
        'current_phase': 'D-documents-vertical',
        'current_item': 'D26-documents-registry-normalized-state',
        'completed_gates': tuple(previous['completed_gates']) + (
            'documents-persistent-provider-neutral-item-registry',
            'documents-folder-parent-normalization',
            'documents-persistent-version-registry',
            'documents-stable-item-identities',
            'documents-stable-version-identities',
            'documents-version-integrity-binding',
            'documents-current-version-state',
            'documents-d26-zero-storage-mutations',
        ),
        'next_item': 'D27-documents-read-list-search-fetch-integration',
        'core_next_gate': 'documents-certified-read-list-search-fetch-integration',
        'documents_write_enabled': False,
        'documents_delete_enabled': False,
        'documents_move_enabled': False,
        'external_calls_made': 0,
    }
