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

router = APIRouter(prefix='/auron/demo1/v21.276', tags=['auron-demo1-post-commit-audit'])

_audit_store: dict[str, dict] = {}


class PostCommitAuditRequest(BaseModel):
    approval_id: UUID
    actor: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    state_receipt: dict


def reset_post_commit_audit_store() -> None:
    _audit_store.clear()


def _scope_matches(item, payload: PostCommitAuditRequest) -> bool:
    return (
        item.arguments.get('session_id') == payload.session_id
        and item.arguments.get('workspace_id') == payload.workspace_id
        and item.requested_by == payload.operator_id
    )


def _audit_fingerprint(payload: PostCommitAuditRequest) -> str:
    raw = json.dumps(
        {
            'approval_id': str(payload.approval_id),
            'session_id': payload.session_id,
            'workspace_id': payload.workspace_id,
            'operator_id': payload.operator_id,
            'state_receipt': payload.state_receipt,
        },
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True,
    )
    return sha256(raw.encode('utf-8')).hexdigest()


def _validate_state_receipt(item, payload: PostCommitAuditRequest, committed: dict | None) -> list[str]:
    receipt = payload.state_receipt
    blockers: list[str] = []

    if receipt.get('approval_id') != str(item.id):
        blockers.append('approval_id')
    if receipt.get('session_id') != payload.session_id:
        blockers.append('session_id')
    if receipt.get('workspace_id') != payload.workspace_id:
        blockers.append('workspace_id')
    if receipt.get('operator_id') != payload.operator_id:
        blockers.append('operator_id')
    if receipt.get('downstream_state_committed') is not True:
        blockers.append('downstream_state_committed')
    if not receipt.get('adapter'):
        blockers.append('adapter')
    if not receipt.get('execution_domain'):
        blockers.append('execution_domain')
    if not receipt.get('state_digest'):
        blockers.append('state_digest')
    if not isinstance(receipt.get('version'), int) or receipt.get('version', 0) < 1:
        blockers.append('version')

    if committed is None:
        blockers.append('committed_state_missing')
        return blockers

    comparisons = {
        'state_digest': committed.get('digest') == receipt.get('state_digest'),
        'version': committed.get('version') == receipt.get('version'),
        'adapter': committed.get('adapter') == receipt.get('adapter'),
        'execution_domain': committed.get('execution_domain') == receipt.get('execution_domain'),
        'adapter_reference': committed.get('adapter_reference') == receipt.get('adapter_reference'),
    }
    blockers.extend(name for name, passed in comparisons.items() if not passed and name not in blockers)
    return blockers


@router.get('/audit-status/{approval_id}')
def audit_status(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')

    committed = _state_store.get(str(approval_id))
    audit = _audit_store.get(str(approval_id))
    return {
        'approval_id': str(item.id),
        'approval_status': item.status.value,
        'downstream_state_present': committed is not None,
        'audit_completed': audit is not None,
        'completion_status': 'completed' if audit else 'pending-audit',
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'next_gate': 'execution-chain-closed' if audit else 'post-commit-audit',
    }


@router.post('/audit')
def audit_post_commit(payload: PostCommitAuditRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    if item.status != ApprovalStatus.consumed:
        raise HTTPException(status_code=409, detail='Post-commit audit is not authorized')

    key = str(item.id)
    committed = _state_store.get(key)
    blockers = _validate_state_receipt(item, payload, committed)
    if blockers:
        return {
            'state': 'post-commit-audit-blocked',
            'approval_id': str(item.id),
            'blockers': blockers,
            'audit_completed': False,
            'completion_status': 'blocked',
            'external_calls_made': 0,
            'business_mutations_made': 0,
            'next_gate': 'downstream-state-reconcile',
        }

    fingerprint = _audit_fingerprint(payload)
    existing = _audit_store.get(key)
    if existing is not None:
        if existing['fingerprint'] != fingerprint:
            return {
                'state': 'post-commit-audit-conflict',
                'approval_id': str(item.id),
                'audit_completed': True,
                'completion_status': 'conflict',
                'external_calls_made': 0,
                'business_mutations_made': 0,
                'next_gate': 'audit-reconciliation',
            }
        return {
            'state': 'post-commit-audit-already-completed',
            'approval_id': str(item.id),
            'audit_receipt': existing['audit_receipt'],
            'audit_completed': True,
            'completion_status': 'completed',
            'idempotent_replay': True,
            'external_calls_made': 0,
            'business_mutations_made': 0,
            'next_gate': 'execution-chain-closed',
        }

    audit_receipt = {
        'approval_id': str(item.id),
        'audited_by': payload.actor,
        'session_id': payload.session_id,
        'workspace_id': payload.workspace_id,
        'operator_id': payload.operator_id,
        'adapter': committed.get('adapter'),
        'execution_domain': committed.get('execution_domain'),
        'adapter_reference': committed.get('adapter_reference'),
        'state_digest': committed.get('digest'),
        'state_version': committed.get('version'),
        'receipt_lineage_verified': True,
        'committed_state_verified': True,
        'execution_chain_complete': True,
    }
    _audit_store[key] = {
        'fingerprint': fingerprint,
        'audit_receipt': audit_receipt,
    }

    return {
        'state': 'post-commit-audit-completed',
        'approval_id': str(item.id),
        'audit_receipt': audit_receipt,
        'audit_completed': True,
        'completion_status': 'completed',
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'audit_records_written': 1,
        'next_gate': 'execution-chain-closed',
        'reply': 'Post-Commit Audit erfolgreich. Receipt-Lineage und Downstream-State stimmen ueberein; die Execution Chain ist abgeschlossen.',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_downstream_state_commit_v21_275 import command_center as v21_275_command_center

    html = v21_275_command_center()
    html = html.replace('v21.275', 'v21.276')
    html = html.replace(
        'AURON DOWNSTREAM STATE COMMIT COMMAND CENTER',
        'AURON POST-COMMIT AUDIT COMMAND CENTER',
    )
    return html
