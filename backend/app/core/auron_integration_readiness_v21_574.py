from __future__ import annotations

from app.core.auron_integration_readiness_v21_573 import get_integration_readiness as get_v21_573_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_573_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.574',
        'current_phase': 'D-documents-vertical',
        'current_item': 'D27-documents-read-list-search-fetch-integration',
        'completed_gates': tuple(previous['completed_gates']) + (
            'documents-onboarding-certified-read-integration',
            'documents-provider-list-sync',
            'documents-provider-search-sync',
            'documents-provider-content-fetch',
            'documents-item-version-identity-verification',
            'documents-content-hash-size-verification',
            'documents-d27-storage-mutations-disabled',
        ),
        'next_item': 'D28-documents-provenance-version-access-policy',
        'core_next_gate': 'documents-provenance-version-access-policy',
        'documents_write_enabled': False,
        'documents_delete_enabled': False,
        'documents_move_enabled': False,
    }
