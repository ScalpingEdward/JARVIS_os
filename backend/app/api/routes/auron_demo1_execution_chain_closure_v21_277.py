from __future__ import annotations

from hashlib import sha256
import json
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.approvals.models import ApprovalStatus
from app.approvals.service import approval_service
from app.api.routes.auron_demo1_downstream_state_commit_v21_275 import _state_store
from app.api.routes.auron_demo1_post_commit_audit_v21_276 import _audit_store

router = APIRouter(prefix='/auron/demo1/v21.277', tags=['auron-demo1-execution-chain-closure'])

_closure_store: dict[str, dict] = {}


class ExecutionChainClosureRequest(BaseModel):
    approval_id: UUID
    actor: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    audit_receipt: dict


def reset_execution_chain_closure_store() -> None:
    _closure_store.clear()


def _scope_matches(item, payload: ExecutionChainClosureRequest) -> bool:
    return (
        item.arguments.get('session_id') == payload.session_id
        and item.arguments.get('workspace_id') == payload.workspace_id
        and item.requested_by == payload.operator_id
    )


def _canonical_digest(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return sha256(raw.encode('utf-8')).hexdigest()


def _validate_audit_receipt(item, payload: ExecutionChainClosureRequest) -> list[str]:
    receipt = payload.audit_receipt
    blockers: list[str] = []

    if receipt.get('approval_id') != str(item.id):
        blockers.append('approval_id')
    if receipt.get('session_id') != payload.session_id:
        blockers.append('session_id')
    if receipt.get('workspace_id') != payload.workspace_id:
        blockers.append('workspace_id')
    if receipt.get('operator_id') != payload.operator_id:
        blockers.append('operator_id')
    if receipt.get('receipt_lineage_verified') is not True:
        blockers.append('receipt_lineage_verified')
    if receipt.get('committed_state_verified') is not True:
        blockers.append('committed_state_verified')
    if receipt.get('execution_chain_complete') is not True:
        blockers.append('execution_chain_complete')
    if not receipt.get('state_digest'):
        blockers.append('state_digest')
    if not isinstance(receipt.get('state_version'), int) or receipt.get('state_version', 0) < 1:
        blockers.append('state_version')
    if not receipt.get('adapter'):
        blockers.append('adapter')
    if not receipt.get('execution_domain'):
        blockers.append('execution_domain')

    key = str(item.id)
    audit_record = _audit_store.get(key)
    committed = _state_store.get(key)

    if audit_record is None:
        blockers.append('audit_record_missing')
    elif audit_record.get('audit_receipt') != receipt:
        blockers.append('audit_receipt_mismatch')

    if committed is None:
        blockers.append('committed_state_missing')
    else:
        comparisons = {
            'state_digest': committed.get('digest') == receipt.get('state_digest'),
            'state_version': committed.get('version') == receipt.get('state_version'),
            'adapter': committed.get('adapter') == receipt.get('adapter'),
            'execution_domain': committed.get('execution_domain') == receipt.get('execution_domain'),
            'adapter_reference': committed.get('adapter_reference') == receipt.get('adapter_reference'),
        }
        blockers.extend(name for name, passed in comparisons.items() if not passed and name not in blockers)

    return blockers


@router.get('/closure-status/{approval_id}')
def closure_status(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')

    closure = _closure_store.get(str(approval_id))
    return {
        'approval_id': str(item.id),
        'approval_status': item.status.value,
        'closed': closure is not None,
        'completion_status': 'finalized' if closure else 'awaiting-closure',
        'snapshot_digest': closure.get('snapshot_digest') if closure else None,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'next_gate': 'execution-lifecycle-finalized' if closure else 'execution-chain-closure',
    }


@router.post('/close')
def close_execution_chain(payload: ExecutionChainClosureRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    if item.status != ApprovalStatus.consumed:
        raise HTTPException(status_code=409, detail='Execution chain closure is not authorized')

    blockers = _validate_audit_receipt(item, payload)
    if blockers:
        return {
            'state': 'execution-chain-closure-blocked',
            'approval_id': str(item.id),
            'blockers': blockers,
            'closed': False,
            'completion_status': 'blocked',
            'external_calls_made': 0,
            'business_mutations_made': 0,
            'next_gate': 'post-commit-audit',
        }

    committed = _state_store[str(item.id)]
    immutable_snapshot = {
        'approval_id': str(item.id),
        'session_id': payload.session_id,
        'workspace_id': payload.workspace_id,
        'operator_id': payload.operator_id,
        'adapter': payload.audit_receipt.get('adapter'),
        'execution_domain': payload.audit_receipt.get('execution_domain'),
        'adapter_reference': payload.audit_receipt.get('adapter_reference'),
        'state_digest': committed.get('digest'),
        'state_version': committed.get('version'),
        'audit_receipt_digest': _canonical_digest(payload.audit_receipt),
        'receipt_lineage_verified': True,
        'committed_state_verified': True,
        'execution_chain_complete': True,
        'lifecycle_finalized': True,
    }
    snapshot_digest = _canonical_digest(immutable_snapshot)

    key = str(item.id)
    existing = _closure_store.get(key)
    if existing is not None:
        if existing.get('snapshot_digest') != snapshot_digest:
            return {
                'state': 'execution-chain-closure-conflict',
                'approval_id': str(item.id),
                'closed': True,
                'completion_status': 'conflict',
                'external_calls_made': 0,
                'business_mutations_made': 0,
                'next_gate': 'closure-reconciliation',
            }
        return {
            'state': 'execution-chain-already-closed',
            'approval_id': str(item.id),
            'closure_receipt': existing['closure_receipt'],
            'immutable_snapshot': existing['immutable_snapshot'],
            'snapshot_digest': existing['snapshot_digest'],
            'closed': True,
            'completion_status': 'finalized',
            'idempotent_replay': True,
            'external_calls_made': 0,
            'business_mutations_made': 0,
            'next_gate': 'execution-lifecycle-finalized',
        }

    closure_receipt = {
        'approval_id': str(item.id),
        'closed_by': payload.actor,
        'session_id': payload.session_id,
        'workspace_id': payload.workspace_id,
        'operator_id': payload.operator_id,
        'snapshot_digest': snapshot_digest,
        'immutable_snapshot_created': True,
        'execution_chain_closed': True,
        'lifecycle_finalized': True,
    }
    _closure_store[key] = {
        'snapshot_digest': snapshot_digest,
        'immutable_snapshot': immutable_snapshot,
        'closure_receipt': closure_receipt,
    }

    return {
        'state': 'execution-chain-closed',
        'approval_id': str(item.id),
        'closure_receipt': closure_receipt,
        'immutable_snapshot': immutable_snapshot,
        'snapshot_digest': snapshot_digest,
        'closed': True,
        'completion_status': 'finalized',
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'closure_records_written': 1,
        'next_gate': 'execution-lifecycle-finalized',
        'reply': 'Execution Chain finalisiert. Ein deterministischer, unveraenderlicher Completion Snapshot wurde erzeugt.',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_post_commit_audit_v21_276 import command_center as v21_276_command_center

    html = v21_276_command_center()
    html = html.replace('v21.276', 'v21.277')
    html = html.replace(
        'AURON POST-COMMIT AUDIT COMMAND CENTER',
        'AURON EXECUTION CHAIN CLOSURE COMMAND CENTER',
    )
    return html
