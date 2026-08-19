from __future__ import annotations
from app.core.auron_integration_readiness_v21_602 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,
        'roadmap_version':'v21.603',
        'current_phase':'G-provider-specific-canary-integration',
        'current_item':'G16-communications-health-drift-command-centre-certification',
        'completed_gates':tuple(previous['completed_gates'])+(
            'communications-persistent-provider-health-evidence',
            'communications-health-evidence-freshness-gate',
            'communications-adapter-descriptor-fingerprint',
            'communications-provider-config-drift-fail-closed',
            'communications-canary-command-centre-read-model',
            'communications-canary-operator-stop-control',
            'communications-canary-command-journal-recorded-not-executed',
            'communications-command-centre-outbound-disabled',),
        'next_item':'G17-next-provider-vertical-selection',
        'core_next_gate':'next-provider-vertical-selection-after-communications',
        'live_transports_enabled':False,
        'communications_outbound_send_enabled':False,
        'communications_provider_write_enabled':False,
        'trading_execution_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
