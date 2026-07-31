from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_completion_observability_v21_279 import _entries, _health

router = APIRouter(prefix='/auron/demo1/v21.280', tags=['auron-demo1-completion-alert-policy'])

_DEFAULT_WARNING_HEALTH_PERCENT = 99.0
_DEFAULT_CRITICAL_HEALTH_PERCENT = 95.0
_DEFAULT_WARNING_FAILURE_COUNT = 1
_DEFAULT_CRITICAL_FAILURE_COUNT = 3


def _policy() -> dict:
    return {
        'warning_health_percent_below': _DEFAULT_WARNING_HEALTH_PERCENT,
        'critical_health_percent_below': _DEFAULT_CRITICAL_HEALTH_PERCENT,
        'warning_failure_count_at_least': _DEFAULT_WARNING_FAILURE_COUNT,
        'critical_failure_count_at_least': _DEFAULT_CRITICAL_FAILURE_COUNT,
        'policy_mode': 'read-only-evaluation',
    }


def _reasons(health: dict) -> list[str]:
    reasons: list[str] = []
    health_percent = float(health.get('health_percent', 100.0))
    failure_count = int(health.get('integrity_failed', 0))

    if health_percent < _DEFAULT_CRITICAL_HEALTH_PERCENT:
        reasons.append('health_percent_below_critical_threshold')
    elif health_percent < _DEFAULT_WARNING_HEALTH_PERCENT:
        reasons.append('health_percent_below_warning_threshold')

    if failure_count >= _DEFAULT_CRITICAL_FAILURE_COUNT:
        reasons.append('failure_count_at_or_above_critical_threshold')
    elif failure_count >= _DEFAULT_WARNING_FAILURE_COUNT:
        reasons.append('failure_count_at_or_above_warning_threshold')
    return reasons


def _severity(health: dict) -> str:
    health_percent = float(health.get('health_percent', 100.0))
    failure_count = int(health.get('integrity_failed', 0))
    if (
        health_percent < _DEFAULT_CRITICAL_HEALTH_PERCENT
        or failure_count >= _DEFAULT_CRITICAL_FAILURE_COUNT
    ):
        return 'critical'
    if (
        health_percent < _DEFAULT_WARNING_HEALTH_PERCENT
        or failure_count >= _DEFAULT_WARNING_FAILURE_COUNT
    ):
        return 'warning'
    return 'ok'


def _evaluate(entries: list[dict]) -> dict:
    health = _health(entries)
    severity = _severity(health)
    reasons = _reasons(health)
    return {
        'severity': severity,
        'signal_active': severity != 'ok',
        'reasons': reasons,
        'health': health,
        'policy': _policy(),
        'operator_action': (
            'investigate-integrity-failures' if severity == 'critical'
            else 'review-integrity-health' if severity == 'warning'
            else 'none'
        ),
    }


@router.get('/policy')
def completion_alert_policy() -> dict:
    return {
        **_policy(),
        'read_only': True,
        'external_calls_made': 0,
        'business_mutations_made': 0,
    }


@router.get('/evaluate')
def evaluate_completion_alert_policy() -> dict:
    result = _evaluate(_entries())
    return {
        **result,
        'read_only': True,
        'notifications_sent': 0,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'terminal_execution_state_modified': False,
    }


@router.get('/signals')
def completion_alert_signals(
    severity: str = Query(default='all', pattern='^(all|ok|warning|critical)$'),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    signals: list[dict] = []
    for entry in _entries():
        if entry.get('integrity_verified'):
            item_severity = 'ok'
            reasons: list[str] = []
        else:
            item_severity = 'critical'
            reasons = []
            if not entry.get('snapshot_digest_matches'):
                reasons.append('snapshot_digest_mismatch')
            if not entry.get('closure_receipt_matches'):
                reasons.append('closure_receipt_mismatch')
            if not entry.get('lifecycle_finalized'):
                reasons.append('lifecycle_not_finalized')

        if severity != 'all' and item_severity != severity:
            continue
        signals.append(
            {
                'approval_id': entry.get('approval_id'),
                'workspace_id': entry.get('workspace_id'),
                'operator_id': entry.get('operator_id'),
                'adapter': entry.get('adapter'),
                'execution_domain': entry.get('execution_domain'),
                'severity': item_severity,
                'signal_active': item_severity != 'ok',
                'reasons': reasons,
            }
        )

    signals.sort(key=lambda value: value.get('approval_id') or '')
    total = len(signals)
    return {
        'count': min(total, limit),
        'total_matching': total,
        'items': signals[:limit],
        'read_only': True,
        'notifications_sent': 0,
        'external_calls_made': 0,
        'business_mutations_made': 0,
    }


@router.get('/dashboard')
def alert_policy_dashboard() -> dict:
    evaluation = _evaluate(_entries())
    return {
        'alert': evaluation,
        'read_only': True,
        'notifications_sent': 0,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'next_layer': 'completion-alert-delivery-boundary',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_completion_observability_v21_279 import command_center as v21_279_command_center

    html = v21_279_command_center()
    html = html.replace('v21.279', 'v21.280')
    html = html.replace(
        'AURON COMPLETION OBSERVABILITY COMMAND CENTER',
        'AURON COMPLETION ALERT POLICY COMMAND CENTER',
    )
    return html
