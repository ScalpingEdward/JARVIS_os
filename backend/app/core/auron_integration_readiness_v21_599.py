from __future__ import annotations
from app.core.auron_integration_readiness_v21_598 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,
        'roadmap_version':'v21.599',
        'current_phase':'G-provider-specific-canary-integration',
        'current_item':'G12-documents-health-drift-command-centre-certification',
        'completed_gates':tuple(previous['completed_gates'])+(
            'documents-persistent-provider-health-evidence',
            'documents-health-evidence-freshness-gate',
            'documents-adapter-descriptor-fingerprint',
            'documents-provider-config-drift-fail-closed',
            'documents-canary-command-centre-read-model',
            'documents-canary-operator-stop-control',
            'documents-canary-command-journal-recorded-not-executed',
            'documents-command-centre-content-mutation-disabled',),
        'next_item':'G13-next-provider-vertical-selection',
        'core_next_gate':'next-provider-vertical-selection-after-documents',
        'live_transports_enabled':False,
        'documents_mutation_enabled':False,
        'documents_delete_enabled':False,
        'documents_move_enabled':False,
        'trading_execution_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
