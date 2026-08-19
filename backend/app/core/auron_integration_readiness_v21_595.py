from __future__ import annotations
from app.core.auron_integration_readiness_v21_594 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,'roadmap_version':'v21.595','current_phase':'G-provider-specific-canary-integration',
        'current_item':'G8-instagram-health-drift-command-centre-certification',
        'completed_gates':tuple(previous['completed_gates'])+(
            'instagram-persistent-provider-health-evidence','instagram-health-evidence-freshness-gate',
            'instagram-adapter-descriptor-fingerprint','instagram-provider-config-drift-fail-closed',
            'instagram-canary-command-centre-read-model','instagram-canary-operator-stop-control',
            'instagram-canary-command-journal-recorded-not-executed','instagram-command-centre-publish-disabled'),
        'next_item':'G9-next-provider-vertical-selection','core_next_gate':'next-provider-vertical-selection-after-instagram',
        'live_transports_enabled':False,'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
