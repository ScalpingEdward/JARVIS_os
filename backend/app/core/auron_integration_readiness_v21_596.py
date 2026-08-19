from __future__ import annotations
from app.core.auron_integration_readiness_v21_595 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,
        'roadmap_version':'v21.596',
        'current_phase':'G-provider-specific-canary-integration',
        'current_item':'G9-next-provider-vertical-selection-files-documents',
        'completed_gates':tuple(previous['completed_gates'])+(
            'next-canary-selection-excludes-already-certified-verticals',
            'next-canary-lowest-risk-safe-local-policy',
            'files-documents-selected-as-third-provider-specific-canary',
            'documents-readonly-preview-scope-only',
            'documents-provider-write-disabled',
            'trading-live-order-placement-remains-ineligible',
            'trading-shadow-deferred-after-lower-risk-local-verticals',),
        'next_item':'G10-documents-readonly-canary-adapter',
        'core_next_gate':'documents-readonly-canary-adapter',
        'live_transports_enabled':False,
        'documents_provider_write_enabled':False,
        'trading_execution_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
