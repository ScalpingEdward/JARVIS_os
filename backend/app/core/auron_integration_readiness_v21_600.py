from __future__ import annotations
from app.core.auron_integration_readiness_v21_599 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,
        'roadmap_version':'v21.600',
        'current_phase':'G-provider-specific-canary-integration',
        'current_item':'G13-next-canary-communications-selection',
        'completed_gates':tuple(previous['completed_gates'])+(
            'research-instagram-documents-provider-canaries-complete',
            'communications-selected-as-next-side-effect-free-local-canary',
            'communications-draft-preview-only-scope',
            'communications-outbound-send-disabled',
            'trading-shadow-deferred-until-communications-complete',
            'trading-live-execution-remains-ineligible',),
        'next_item':'G14-communications-draft-canary-adapter',
        'core_next_gate':'communications-draft-canary-adapter',
        'live_transports_enabled':False,
        'communications_outbound_send_enabled':False,
        'provider_write_enabled':False,
        'trading_execution_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
