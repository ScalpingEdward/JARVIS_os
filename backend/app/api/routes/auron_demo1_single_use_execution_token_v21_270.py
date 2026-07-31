from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.approvals.models import ApprovalStatus
from app.approvals.service import approval_service

v21_270_router = APIRouter(prefix='/auron/demo1/v21.270', tags=['auron-demo1-single-use-execution-token'])

_TOKEN_TTL_SECONDS = 120
_token_store: dict[str, dict] = {}


class ExecutionTokenIssueRequest(BaseModel):
    approval_id: UUID
    actor: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    arm_receipt: dict


class ExecutionTokenConsumeRequest(BaseModel):
    approval_id: UUID
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    token: str = Field(min_length=20, max_length=500)


def reset_token_store() -> None:
    _token_store.clear()


def _scope_matches(item, session_id: str, workspace_id: str, operator_id: str) -> bool:
    return (
        item.arguments.get('session_id') == session_id
        and item.arguments.get('workspace_id') == workspace_id
        and item.requested_by == operator_id
    )


def _validate_arm_receipt(item, payload: ExecutionTokenIssueRequest) -> list[str]:
    receipt = payload.arm_receipt
    blockers: list[str] = []
    if receipt.get('approval_id') != str(item.id): blockers.append('approval_id')
    if receipt.get('session_id') != payload.session_id: blockers.append('session_id')
    if receipt.get('workspace_id') != payload.workspace_id: blockers.append('workspace_id')
    if receipt.get('operator_id') != payload.operator_id: blockers.append('operator_id')
    if receipt.get('armed') is not True: blockers.append('armed')
    if receipt.get('operator_confirmed') is not True: blockers.append('operator_confirmed')
    if receipt.get('safety_checks_passed') is not True: blockers.append('safety_checks_passed')
    if not receipt.get('adapter'): blockers.append('adapter')
    if not receipt.get('execution_domain'): blockers.append('execution_domain')
    return blockers


def _digest(token: str) -> str:
    return sha256(token.encode('utf-8')).hexdigest()


@v21_270_router.get('/token-status/{approval_id}')
def token_status(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    record = _token_store.get(str(approval_id))
    now = datetime.now(timezone.utc)
    active = bool(record and not record['used'] and record['expires_at'] > now)
    return {
        'approval_id': str(item.id),
        'approval_status': item.status.value,
        'token_active': active,
        'token_used': bool(record and record['used']),
        'execution_performed': False,
        'adapter_invoked': False,
        'next_gate': 'single-use-token-issue' if not active else 'single-use-token-consume',
    }


@v21_270_router.post('/issue')
def issue_token(payload: ExecutionTokenIssueRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload.session_id, payload.workspace_id, payload.operator_id):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    if item.status != ApprovalStatus.consumed:
        raise HTTPException(status_code=409, detail='Execution token issuance is not authorized')
    blockers = _validate_arm_receipt(item, payload)
    if blockers:
        return {'state': 'token-issuance-blocked', 'approval_id': str(item.id), 'blockers': blockers, 'execution_performed': False, 'adapter_invoked': False, 'next_gate': 'live-execution-arm-gate'}
    existing = _token_store.get(str(item.id))
    now = datetime.now(timezone.utc)
    if existing and not existing['used'] and existing['expires_at'] > now:
        raise HTTPException(status_code=409, detail='Active execution token already exists')
    token = token_urlsafe(32)
    expires_at = now + timedelta(seconds=_TOKEN_TTL_SECONDS)
    _token_store[str(item.id)] = {
        'digest': _digest(token), 'session_id': payload.session_id, 'workspace_id': payload.workspace_id,
        'operator_id': payload.operator_id, 'adapter': payload.arm_receipt.get('adapter'),
        'execution_domain': payload.arm_receipt.get('execution_domain'), 'expires_at': expires_at, 'used': False,
    }
    return {'state': 'single-use-token-issued', 'approval_id': str(item.id), 'execution_token': token, 'expires_at': expires_at.isoformat(), 'single_use': True, 'execution_performed': False, 'adapter_invoked': False, 'next_gate': 'single-use-token-consume', 'reply': 'Ein einmaliger Execution Token wurde ausgestellt. Es wurde noch keine Live-Aktion ausgefuehrt.'}


@v21_270_router.post('/consume')
def consume_token(payload: ExecutionTokenConsumeRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload.session_id, payload.workspace_id, payload.operator_id):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    record = _token_store.get(str(item.id))
    if record is None: raise HTTPException(status_code=404, detail='Execution token not found')
    if record['used']: raise HTTPException(status_code=409, detail='Execution token already used')
    if record['expires_at'] <= datetime.now(timezone.utc): raise HTTPException(status_code=409, detail='Execution token expired')
    if record['session_id'] != payload.session_id or record['workspace_id'] != payload.workspace_id or record['operator_id'] != payload.operator_id:
        raise HTTPException(status_code=403, detail='Execution token scope mismatch')
    if record['digest'] != _digest(payload.token): raise HTTPException(status_code=403, detail='Invalid execution token')
    record['used'] = True
    authorization_receipt = {
        'approval_id': str(item.id), 'session_id': payload.session_id, 'workspace_id': payload.workspace_id,
        'operator_id': payload.operator_id, 'adapter': record['adapter'], 'execution_domain': record['execution_domain'],
        'token_consumed': True, 'single_use_enforced': True,
    }
    return {'state': 'execution-token-consumed', 'approval_id': str(item.id), 'authorization_receipt': authorization_receipt, 'execution_performed': False, 'adapter_invoked': False, 'next_gate': 'controlled-adapter-boundary', 'reply': 'One-Shot-Autorisierung konsumiert. Die Live-Aktion selbst wurde noch nicht ausgefuehrt.'}


@v21_270_router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_live_execution_arm_gate_v21_269 import command_center as v21_269_command_center
    html = v21_269_command_center()
    html = html.replace('v21.269', 'v21.270')
    html = html.replace('AURON LIVE EXECUTION ARM GATE COMMAND CENTER', 'AURON SINGLE-USE EXECUTION TOKEN COMMAND CENTER')
    return html


# Composite registration keeps app.main stable while exposing the next isolated gates.
from app.api.routes.auron_demo1_controlled_adapter_boundary_v21_271 import router as v21_271_router
from app.api.routes.auron_demo1_adapter_call_commit_v21_272 import router as v21_272_router
from app.api.routes.auron_demo1_adapter_call_dispatch_v21_273 import router as v21_273_router
from app.api.routes.auron_demo1_adapter_result_verification_v21_274 import router as v21_274_router
from app.api.routes.auron_demo1_downstream_state_commit_v21_275 import router as v21_275_router

router = APIRouter()
router.include_router(v21_270_router)
router.include_router(v21_271_router)
router.include_router(v21_272_router)
router.include_router(v21_273_router)
router.include_router(v21_274_router)
router.include_router(v21_275_router)
