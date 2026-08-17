from __future__ import annotations

from app.core.auron_integration_readiness_v21_560 import get_integration_readiness as get_v21_560_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_560_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.561',
        'current_phase': 'D-research-vertical',
        'current_item': 'D14-controlled-research-watch-execution',
        'completed_gates': tuple(previous['completed_gates']) + (
            'research-persistent-watch-policy',
            'research-explicit-watch-cadence',
            'research-operator-watch-enablement',
            'research-watch-kill-switch',
            'research-provider-identity-bound-watch',
            'research-idempotent-watch-run-id',
            'research-governed-d11-read-per-watch-run',
            'research-d13-report-simulation-per-watch-run',
            'research-zero-downstream-actions-from-watch',
        ),
        'next_item': 'D15-research-reconciliation-freshness-retry',
        'core_next_gate': 'research-watch-reconciliation-freshness-retry',
        'research_watch_capability_available': True,
        'research_unattended_actions_enabled': False,
        'research_downstream_execution_enabled': False,
        'external_calls_made': 0,
    }
