from __future__ import annotations
from app.core.auron_integration_readiness_v21_590 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,
        'roadmap_version':'v21.591',
        'current_phase':'G-provider-specific-canary-integration',
        'current_item':'G4-provider-specific-canary-command-centre-controls',
        'completed_gates':tuple(previous['completed_gates'])+(
            'research-canary-command-centre-read-model',
            'research-adapter-descriptor-visible',
            'research-health-evidence-visible',
            'research-canary-execution-reconciliation-visible',
            'research-stop-control-exposed',
            'research-health-certification-control-exposed',
            'research-command-journal-recorded-not-executed',
            'research-command-centre-production-transport-disabled',),
        'next_item':'G5-next-provider-vertical-selection',
        'core_next_gate':'next-provider-vertical-selection',
        'live_transports_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
