from __future__ import annotations
from app.core.auron_integration_readiness_v21_589 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,'roadmap_version':'v21.590','current_phase':'G-provider-specific-canary-integration',
        'current_item':'G3-research-provider-health-drift-certification',
        'completed_gates':tuple(previous['completed_gates'])+(
            'research-persistent-provider-health-evidence','research-health-evidence-freshness-gate',
            'research-adapter-config-fingerprint','research-provider-identity-drift-detection',
            'research-adapter-config-drift-fail-closed','research-unhealthy-provider-fail-closed'),
        'next_item':'G4-provider-specific-canary-command-centre-controls',
        'core_next_gate':'provider-specific-canary-command-centre-controls',
        'live_transports_enabled':False,'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
