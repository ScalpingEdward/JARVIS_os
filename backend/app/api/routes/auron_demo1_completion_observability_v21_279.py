from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_completion_registry_v21_278 import _entry
from app.api.routes.auron_demo1_execution_chain_closure_v21_277 import _closure_store

router = APIRouter(prefix='/auron/demo1/v21.279', tags=['auron-demo1-completion-observability'])


def _entries() -> list[dict]:
    return [_entry(approval_id, record) for approval_id, record in _closure_store.items()]


def _health(entries: list[dict]) -> dict:
    total = len(entries)
    verified = sum(1 for entry in entries if entry.get('integrity_verified'))
    failed = total - verified
    health_pct = round((verified / total) * 100, 2) if total else 100.0
    if failed == 0:
        status = 'healthy'
    elif verified == 0:
        status = 'critical'
    else:
        status = 'degraded'
    return {
        'status': status,
        'health_percent': health_pct,
        'finalized_executions': total,
        'integrity_verified': verified,
        'integrity_failed': failed,
    }


def _dimension(entries: list[dict], field: str) -> list[dict]:
    totals = Counter(entry.get(field) or 'unknown' for entry in entries)
    failures = Counter(
        entry.get(field) or 'unknown'
        for entry in entries
        if not entry.get('integrity_verified')
    )
    result: list[dict] = []
    for value in sorted(totals):
        total = totals[value]
        failed = failures[value]
        verified = total - failed
        result.append(
            {
                field: value,
                'total': total,
                'verified': verified,
                'failed': failed,
                'health_percent': round((verified / total) * 100, 2) if total else 100.0,
            }
        )
    return result


@router.get('/health')
def completion_health() -> dict:
    entries = _entries()
    return {
        **_health(entries),
        'read_only': True,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'lifecycle_state': 'terminal-observability',
    }


@router.get('/metrics')
def completion_metrics() -> dict:
    entries = _entries()
    health = _health(entries)
    return {
        'health': health,
        'by_workspace': _dimension(entries, 'workspace_id'),
        'by_operator': _dimension(entries, 'operator_id'),
        'by_adapter': _dimension(entries, 'adapter'),
        'by_execution_domain': _dimension(entries, 'execution_domain'),
        'read_only': True,
        'external_calls_made': 0,
        'business_mutations_made': 0,
    }


@router.get('/integrity-failures')
def integrity_failures(
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    failures: list[dict] = []
    for entry in _entries():
        if entry.get('integrity_verified'):
            continue
        reasons: list[str] = []
        if not entry.get('snapshot_digest_matches'):
            reasons.append('snapshot_digest_mismatch')
        if not entry.get('closure_receipt_matches'):
            reasons.append('closure_receipt_mismatch')
        if not entry.get('lifecycle_finalized'):
            reasons.append('lifecycle_not_finalized')
        failures.append(
            {
                'approval_id': entry.get('approval_id'),
                'workspace_id': entry.get('workspace_id'),
                'operator_id': entry.get('operator_id'),
                'adapter': entry.get('adapter'),
                'execution_domain': entry.get('execution_domain'),
                'stored_snapshot_digest': entry.get('stored_snapshot_digest'),
                'calculated_snapshot_digest': entry.get('calculated_snapshot_digest'),
                'reasons': reasons,
            }
        )

    failures.sort(key=lambda value: value['approval_id'] or '')
    total = len(failures)
    failures = failures[:limit]
    return {
        'count': len(failures),
        'total_failures': total,
        'items': failures,
        'read_only': True,
        'external_calls_made': 0,
        'business_mutations_made': 0,
    }


@router.get('/dashboard')
def observability_dashboard() -> dict:
    entries = _entries()
    health = _health(entries)
    failures = [entry for entry in entries if not entry.get('integrity_verified')]
    return {
        'health': health,
        'failure_count': len(failures),
        'workspace_count': len({entry.get('workspace_id') for entry in entries if entry.get('workspace_id')}),
        'operator_count': len({entry.get('operator_id') for entry in entries if entry.get('operator_id')}),
        'adapter_count': len({entry.get('adapter') for entry in entries if entry.get('adapter')}),
        'execution_domain_count': len({entry.get('execution_domain') for entry in entries if entry.get('execution_domain')}),
        'read_only': True,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'next_layer': 'completion-alert-policy',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_completion_registry_v21_278 import command_center as v21_278_command_center

    html = v21_278_command_center()
    html = html.replace('v21.278', 'v21.279')
    html = html.replace(
        'AURON COMPLETION REGISTRY COMMAND CENTER',
        'AURON COMPLETION OBSERVABILITY COMMAND CENTER',
    )
    return html
