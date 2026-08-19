from __future__ import annotations
from app.core.auron_integration_readiness_v21_591 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,
        'roadmap_version':'v21.592',
        'current_phase':'G-provider-specific-canary-integration',
        'current_item':'G5-next-provider-vertical-selection',
        'completed_gates':tuple(previous['completed_gates'])+(
            'next-canary-risk-utility-policy',
            'instagram-content-selected-as-second-canary-vertical',
            'instagram-draft-preview-only-scope',
            'instagram-public-publish-disabled',
            'trading-live-execution-deferred',),
        'next_item':'G6-instagram-draft-preview-canary-adapter',
        'core_next_gate':'instagram-draft-preview-canary-adapter',
        'live_transports_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'instagram_publish_enabled':False,
        'trading_execution_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
