from __future__ import annotations

from app.core.auron_integration_readiness_v21_571 import get_integration_readiness as get_v21_571_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_571_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.572',
        'current_phase': 'D-documents-vertical',
        'current_item': 'D25-documents-provider-adapter-onboarding-contract',
        'completed_gates': tuple(previous['completed_gates']) + (
            'documents-vertical-selected',
            'documents-provider-identity-contract',
            'documents-read-only-permission-contract',
            'documents-metadata-content-inspection-contract',
            'documents-stable-version-identity-contract',
            'documents-d25-write-delete-disabled',
        ),
        'next_item': 'D26-documents-registry-normalized-state',
        'core_next_gate': 'documents-persistent-file-folder-version-registry',
        'documents_write_enabled': False,
        'documents_delete_enabled': False,
    }
