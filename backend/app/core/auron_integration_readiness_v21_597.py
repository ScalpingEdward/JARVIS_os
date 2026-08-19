from __future__ import annotations
from app.core.auron_integration_readiness_v21_596 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,'roadmap_version':'v21.597','current_phase':'G-provider-specific-canary-integration',
        'current_item':'G10-documents-readonly-canary-adapter',
        'completed_gates':tuple(previous['completed_gates'])+(
            'documents-readonly-adapter-implemented','documents-F2-execution-compatible',
            'documents-F3-result-reader-compatible','documents-F3-stop-compatible',
            'documents-metadata-version-preview-persistent','documents-content-read-disabled',
            'documents-mutation-delete-move-disabled','documents-external-calls-zero'),
        'next_item':'G11-documents-canary-end-to-end-certification',
        'core_next_gate':'documents-canary-end-to-end-certification',
        'live_transports_enabled':False,'documents_mutation_enabled':False,
        'documents_delete_enabled':False,'documents_move_enabled':False,
        'trading_execution_enabled':False,'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
