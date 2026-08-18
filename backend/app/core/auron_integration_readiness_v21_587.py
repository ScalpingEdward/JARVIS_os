from __future__ import annotations
from app.core.auron_integration_readiness_v21_586 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    previous=previous_readiness()
    return {**previous,
        'roadmap_version':'v21.587',
        'current_phase':'F-controlled-provider-canary-program',
        'current_item':'F4-canary-certification-promotion-rollback-decision',
        'completed_gates':tuple(previous['completed_gates'])+(
            'canary-certification-evidence-revalidation',
            'canary-all-submitted-actions-reconciled-required',
            'canary-stop-forces-rollback',
            'canary-stop-failure-forces-rollback',
            'canary-health-policy-recheck-before-promotion',
            'canary-explicit-promotion-approval',
            'canary-promotion-artifact-separate-from-transport',
            'canary-F1-F4-program-architecture-complete',),
        'next_item':'G1-provider-specific-canary-adapter-selection',
        'core_next_gate':'provider-specific-canary-adapter-selection',
        'live_transports_enabled':False,
        'unrestricted_production_transport_enabled':False,
        'production_canary_auto_activation_enabled':False,
        'cross_vertical_direct_provider_bypass_allowed':False}
