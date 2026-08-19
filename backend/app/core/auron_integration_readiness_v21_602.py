from __future__ import annotations
from app.core.auron_integration_readiness_v21_601 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,'roadmap_version':'v21.602','current_phase':'G-provider-specific-canary-integration',
        'current_item':'G15-communications-canary-end-to-end-certification',
        'completed_gates':tuple(previous['completed_gates'])+(
            'communications-F1-F2-G14-F3-F4-chain-wired','communications-provider-specific-identity-bound',
            'communications-draft-action-e2e-certified','communications-immediate-result-reconciliation-e2e',
            'communications-promotion-hold-artifact-e2e','communications-outbound-send-e2e-disabled',
            'communications-provider-write-e2e-disabled','communications-network-production-e2e-disabled',
            'communications-zero-external-calls-e2e'),
        'next_item':'G16-communications-health-drift-command-centre-certification',
        'core_next_gate':'communications-health-drift-command-centre-certification',
        'live_transports_enabled':False,'communications_outbound_send_enabled':False,
        'communications_provider_write_enabled':False,'trading_execution_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
