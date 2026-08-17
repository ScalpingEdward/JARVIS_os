from __future__ import annotations

from app.core.auron_integration_readiness_v21_561 import get_integration_readiness as get_v21_561_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_561_readiness()
    return {
        **previous,
        'roadmap_version': 'v21.562',
        'current_phase': 'D-research-vertical',
        'current_item': 'D15-research-watch-reconciliation-freshness-retry',
        'completed_gates': tuple(previous['completed_gates']) + (
            'research-watch-run-reconciliation',
            'research-post-run-source-freshness-verification',
            'research-stale-evidence-fail-closed',
            'research-bounded-retry-policy',
            'research-exponential-retry-backoff',
            'research-retry-reenters-d14-policy-boundary',
            'research-reconciliation-zero-downstream-actions',
        ),
        'next_item': 'D16-research-command-centre-operations',
        'core_next_gate': 'research-command-centre-operational-visibility-controls',
        'research_unattended_actions_enabled': False,
        'research_downstream_execution_enabled': False,
        'external_calls_made': 0,
    }
