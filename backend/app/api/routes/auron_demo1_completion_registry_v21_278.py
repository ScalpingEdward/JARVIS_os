from __future__ import annotations

from hashlib import sha256
import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.approvals.service import approval_service
from app.api.routes.auron_demo1_execution_chain_closure_v21_277 import _closure_store

router = APIRouter(prefix='/auron/demo1/v21.278', tags=['auron-demo1-completion-registry'])


def _canonical_digest(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return sha256(raw.encode('utf-8')).hexdigest()


def _integrity_status(record: dict) -> dict:
    snapshot = record.get('immutable_snapshot')
    stored_digest = record.get('snapshot_digest')
    calculated_digest = _canonical_digest(snapshot) if isinstance(snapshot, dict) else None
    closure_receipt = record.get('closure_receipt') or {}
    receipt_digest_matches = closure_receipt.get('snapshot_digest') == stored_digest
    snapshot_digest_matches = bool(stored_digest and calculated_digest == stored_digest)
    immutable_flag_present = snapshot.get('lifecycle_finalized') is True if isinstance(snapshot, dict) else False
    return {
        'integrity_verified': snapshot_digest_matches and receipt_digest_matches and immutable_flag_present,
        'stored_snapshot_digest': stored_digest,
        'calculated_snapshot_digest': calculated_digest,
        'snapshot_digest_matches': snapshot_digest_matches,
        'closure_receipt_matches': receipt_digest_matches,
        'lifecycle_finalized': immutable_flag_present,
    }


def _entry(approval_id: str, record: dict, include_snapshot: bool = False) -> dict:
    snapshot = record.get('immutable_snapshot') or {}
    integrity = _integrity_status(record)
    result = {
        'approval_id': approval_id,
        'session_id': snapshot.get('session_id'),
        'workspace_id': snapshot.get('workspace_id'),
        'operator_id': snapshot.get('operator_id'),
        'adapter': snapshot.get('adapter'),
        'execution_domain': snapshot.get('execution_domain'),
        'adapter_reference': snapshot.get('adapter_reference'),
        'state_digest': snapshot.get('state_digest'),
        'state_version': snapshot.get('state_version'),
        'snapshot_digest': record.get('snapshot_digest'),
        'completion_status': 'finalized',
        **integrity,
    }
    if include_snapshot:
        result['immutable_snapshot'] = snapshot
        result['closure_receipt'] = record.get('closure_receipt')
    return result


def _matches(entry: dict, workspace_id: str | None, operator_id: str | None, adapter: str | None, execution_domain: str | None) -> bool:
    filters = {
        'workspace_id': workspace_id,
        'operator_id': operator_id,
        'adapter': adapter,
        'execution_domain': execution_domain,
    }
    return all(value is None or entry.get(name) == value for name, value in filters.items())


@router.get('/completion/{approval_id}')
def completion_detail(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    record = _closure_store.get(str(approval_id))
    if record is None:
        raise HTTPException(status_code=404, detail='Completion snapshot not found')
    return {
        **_entry(str(approval_id), record, include_snapshot=True),
        'approval_status': item.status.value,
        'read_only': True,
        'external_calls_made': 0,
        'business_mutations_made': 0,
    }


@router.get('/completions')
def completion_list(
    workspace_id: str | None = Query(default=None, max_length=120),
    operator_id: str | None = Query(default=None, max_length=120),
    adapter: str | None = Query(default=None, max_length=160),
    execution_domain: str | None = Query(default=None, max_length=160),
    integrity: str = Query(default='all', pattern='^(all|verified|failed)$'),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    entries: list[dict] = []
    for approval_id, record in _closure_store.items():
        entry = _entry(approval_id, record)
        if not _matches(entry, workspace_id, operator_id, adapter, execution_domain):
            continue
        if integrity == 'verified' and not entry['integrity_verified']:
            continue
        if integrity == 'failed' and entry['integrity_verified']:
            continue
        entries.append(entry)

    entries.sort(key=lambda value: value['approval_id'])
    total = len(entries)
    entries = entries[:limit]
    return {
        'count': len(entries),
        'total_matching': total,
        'items': entries,
        'read_only': True,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'next_layer': 'completion-observability',
    }


@router.get('/summary')
def completion_summary() -> dict:
    finalized = 0
    verified = 0
    failed = 0
    workspaces: set[str] = set()
    adapters: set[str] = set()
    domains: set[str] = set()

    for approval_id, record in _closure_store.items():
        entry = _entry(approval_id, record)
        finalized += 1
        if entry['integrity_verified']:
            verified += 1
        else:
            failed += 1
        if entry.get('workspace_id'):
            workspaces.add(entry['workspace_id'])
        if entry.get('adapter'):
            adapters.add(entry['adapter'])
        if entry.get('execution_domain'):
            domains.add(entry['execution_domain'])

    return {
        'finalized_executions': finalized,
        'integrity_verified': verified,
        'integrity_failed': failed,
        'workspaces': sorted(workspaces),
        'adapters': sorted(adapters),
        'execution_domains': sorted(domains),
        'read_only': True,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'lifecycle_state': 'terminal-snapshots-indexed',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_execution_chain_closure_v21_277 import command_center as v21_277_command_center

    html = v21_277_command_center()
    html = html.replace('v21.277', 'v21.278')
    html = html.replace(
        'AURON EXECUTION CHAIN CLOSURE COMMAND CENTER',
        'AURON COMPLETION REGISTRY COMMAND CENTER',
    )
    return html
