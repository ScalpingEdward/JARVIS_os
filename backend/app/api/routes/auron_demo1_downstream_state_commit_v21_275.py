from __future__ import annotations

from hashlib import sha256
import json
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.approvals.models import ApprovalStatus
from app.approvals.service import approval_service

router = APIRouter(prefix='/auron/demo1/v21.275', tags=['auron-demo1-downstream-state-commit'])

_state_store: dict[str, dict] = {}


class DownstreamStateCommitRequest(BaseModel):
    approval_id: UUID
    actor: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    verification_receipt: dict
    downstream_state: dict = Field(default_factory=dict)
    expected_version: int = Field(default=0, ge=0)
    commit: bool = True


def reset_downstream_state_store() -> None:
    _state_store.clear()


def _scope_matches(item, payload: DownstreamStateCommitRequest) -> bool:
    return (
        item.arguments.get('session_id') == payload.session_id
        and item.arguments.get('workspace_id') == payload.workspace_id
        and item.requested_by == payload.operator_id
    )


def _validate_verification_receipt(item, payload: DownstreamStateCommitRequest) -> list[str]:
    receipt = payload.verification_receipt
    blockers: list[str] = []
    if receipt.get('approval_id') != str(item.id):
        blockers.append('approval_id')
    if receipt.get('session_id') != payload.session_id:
        blockers.append('session_id')
    if receipt.get('workspace_id') != payload.workspace_id:
        blockers.append('workspace_id')
    if receipt.get('operator_id') != payload.operator_id:
        blockers.append('operator_id')
    if receipt.get('dispatch_verified') is not True:
        blockers.append('dispatch_verified')
    if receipt.get('adapter_result_verified') is not True:
        blockers.append('adapter_result_verified')
    if not receipt.get('adapter'):
        blockers.append('adapter')
    if not receipt.get('execution_domain'):
        blockers.append('execution_domain')
    return blockers


def _state_digest(state: dict) -> str:
    raw = json.dumps(state, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return sha256(raw.encode('utf-8')).hexdigest()


@router.get('/state/{approval_id}')
def downstream_state(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    record = _state_store.get(str(approval_id))
    return {
        'approval_id': str(item.id),
        'approval_status': item.status.value,
        'state_committed': record is not None,
        'version': record['version'] if record else 0,
        'state': record['state'] if record else None,
        'external_calls_made': 0,
        'next_gate': 'downstream-state-commit' if record is None else 'post-commit-audit',
    }


@router.post('/commit')
def commit_downstream_state(payload: DownstreamStateCommitRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    if item.status != ApprovalStatus.consumed:
        raise HTTPException(status_code=409, detail='Downstream state commit is not authorized')

    receipt_blockers = _validate_verification_receipt(item, payload)
    if receipt_blockers:
        return {
            'state': 'downstream-state-commit-blocked',
            'approval_id': str(item.id),
            'blockers': receipt_blockers,
            'external_calls_made': 0,
            'mutations_made': 0,
            'next_gate': 'adapter-result-verification',
        }

    if payload.commit is not True:
        return {
            'state': 'downstream-state-commit-declined',
            'approval_id': str(item.id),
            'external_calls_made': 0,
            'mutations_made': 0,
            'next_gate': 'adapter-result-verification',
        }

    key = str(item.id)
    existing = _state_store.get(key)
    current_version = existing['version'] if existing else 0
    digest = _state_digest(payload.downstream_state)

    if existing and existing['digest'] == digest:
        return {
            'state': 'downstream-state-already-committed',
            'approval_id': str(item.id),
            'version': existing['version'],
            'state_digest': digest,
            'external_calls_made': 0,
            'mutations_made': 0,
            'idempotent_replay': True,
            'next_gate': 'post-commit-audit',
        }

    if payload.expected_version != current_version:
        return {
            'state': 'downstream-state-version-conflict',
            'approval_id': str(item.id),
            'expected_version': payload.expected_version,
            'current_version': current_version,
            'external_calls_made': 0,
            'mutations_made': 0,
            'next_gate': 'downstream-state-reconcile',
        }

    new_version = current_version + 1
    _state_store[key] = {
        'version': new_version,
        'digest': digest,
        'state': payload.downstream_state,
        'committed_by': payload.actor,
        'adapter': payload.verification_receipt.get('adapter'),
        'execution_domain': payload.verification_receipt.get('execution_domain'),
        'adapter_reference': payload.verification_receipt.get('adapter_reference'),
    }

    state_receipt = {
        'approval_id': str(item.id),
        'committed_by': payload.actor,
        'session_id': payload.session_id,
        'workspace_id': payload.workspace_id,
        'operator_id': payload.operator_id,
        'adapter': payload.verification_receipt.get('adapter'),
        'execution_domain': payload.verification_receipt.get('execution_domain'),
        'adapter_reference': payload.verification_receipt.get('adapter_reference'),
        'state_digest': digest,
        'version': new_version,
        'downstream_state_committed': True,
    }
    return {
        'state': 'downstream-state-committed',
        'approval_id': str(item.id),
        'state_receipt': state_receipt,
        'external_calls_made': 0,
        'mutations_made': 1,
        'next_gate': 'post-commit-audit',
        'reply': 'Verifiziertes Adapter-Ergebnis wurde kontrolliert in den internen Downstream-State committed.',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_adapter_result_verification_v21_274 import command_center as v21_274_command_center

    html = v21_274_command_center()
    html = html.replace('v21.274', 'v21.275')
    html = html.replace(
        'AURON ADAPTER RESULT VERIFICATION COMMAND CENTER',
        'AURON DOWNSTREAM STATE COMMIT COMMAND CENTER',
    )
    return html
