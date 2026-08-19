from __future__ import annotations
from app.core.auron_integration_readiness_v21_600 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,
        'roadmap_version':'v21.601',
        'current_phase':'G-provider-specific-canary-integration',
        'current_item':'G14-communications-draft-canary-adapter',
        'completed_gates':tuple(previous['completed_gates'])+(
            'communications-draft-canary-adapter-integrated',
            'communications-F2-execution-compatible',
            'communications-F3-result-reader-compatible',
            'communications-F3-stop-compatible',
            'communications-local-preview-state-persistent',
            'communications-recipient-plan-state-persistent',
            'communications-outbound-send-disabled',
            'communications-provider-write-disabled',
            'communications-network-transport-disabled',),
        'next_item':'G15-communications-canary-end-to-end-certification',
        'core_next_gate':'communications-canary-end-to-end-certification',
        'live_transports_enabled':False,
        'communications_outbound_send_enabled':False,
        'trading_execution_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
