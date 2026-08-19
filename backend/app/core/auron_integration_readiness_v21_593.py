from __future__ import annotations
from app.core.auron_integration_readiness_v21_592 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,
        'roadmap_version':'v21.593',
        'current_phase':'G-provider-specific-canary-integration',
        'current_item':'G6-instagram-draft-preview-canary-adapter',
        'completed_gates':tuple(previous['completed_gates'])+(
            'instagram-draft-preview-canary-adapter-integrated',
            'instagram-draft-preview-f2-execution-compatible',
            'instagram-draft-preview-f3-result-reader-compatible',
            'instagram-draft-preview-f3-stop-boundary-compatible',
            'instagram-local-preview-state-persistent',
            'instagram-public-publish-disabled',
            'instagram-provider-write-disabled',
            'instagram-network-transport-disabled',),
        'next_item':'G7-instagram-draft-preview-end-to-end-certification',
        'core_next_gate':'instagram-draft-preview-provider-specific-e2e-certification',
        'live_transports_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
