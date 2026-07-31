from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.approvals.models import ApprovalStatus
from app.approvals.service import approval_service

router = APIRouter(prefix='/auron/demo1/v21.274', tags=['auron-demo1-adapter-result-verification'])


class AdapterResultVerificationRequest(BaseModel):
    approval_id: UUID
    actor: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    dispatch_receipt: dict
    adapter_result: dict
    require_ok: bool = True
    expected_reference: str | None = Field(default=None, max_length=250)


def _scope_matches(item, payload: AdapterResultVerificationRequest) -> bool:
    return (
        item.arguments.get('session_id') == payload.session_id
        and item.arguments.get('workspace_id') == payload.workspace_id
        and item.requested_by == payload.operator_id
    )


def _validate_dispatch_receipt(item, payload: AdapterResultVerificationRequest) -> list[str]:
    receipt = payload.dispatch_receipt
    blockers: list[str] = []
    if receipt.get('approval_id') != str(item.id):
        blockers.append('approval_id')
    if receipt.get('session_id') != payload.session_id:
        blockers.append('session_id')
    if receipt.get('workspace_id') != payload.workspace_id:
        blockers.append('workspace_id')
    if receipt.get('operator_id') != payload.operator_id:
        blockers.append('operator_id')
    if receipt.get('call_committed') is not True:
        blockers.append('call_committed')
    if receipt.get('adapter_invoked') is not True:
        blockers.append('adapter_invoked')
    if receipt.get('external_calls_made') != 1:
        blockers.append('external_calls_made')
    if not receipt.get('adapter'):
        blockers.append('adapter')
    if not receipt.get('execution_domain'):
        blockers.append('execution_domain')
    return blockers


def _verify_result(payload: AdapterResultVerificationRequest) -> dict:
    checks: dict[str, bool] = {
        'result_is_mapping': isinstance(payload.adapter_result, dict),
        'result_present': bool(payload.adapter_result),
    }
    if payload.require_ok:
        checks['result_ok'] = payload.adapter_result.get('ok') is True
    if payload.expected_reference is not None:
        checks['reference_matches'] = payload.adapter_result.get('reference') == payload.expected_reference
    blockers = [name for name, passed in checks.items() if not passed]
    return {'checks': checks, 'blockers': blockers, 'verified': not blockers}


@router.get('/verification-status/{approval_id}')
def verification_status(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    return {
        'approval_id': str(item.id),
        'approval_status': item.status.value,
        'verification_available': item.status == ApprovalStatus.consumed,
        'external_calls_made': 0,
        'mutations_made': 0,
        'next_gate': 'adapter-result-verification',
    }


@router.post('/verify')
def verify_adapter_result(payload: AdapterResultVerificationRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    if item.status != ApprovalStatus.consumed:
        raise HTTPException(status_code=409, detail='Adapter result verification is not authorized')

    receipt_blockers = _validate_dispatch_receipt(item, payload)
    if receipt_blockers:
        return {
            'state': 'adapter-result-verification-blocked',
            'approval_id': str(item.id),
            'blockers': receipt_blockers,
            'external_calls_made': 0,
            'mutations_made': 0,
            'next_gate': 'adapter-call-dispatch',
        }

    verification = _verify_result(payload)
    if not verification['verified']:
        return {
            'state': 'adapter-result-rejected',
            'approval_id': str(item.id),
            **verification,
            'external_calls_made': 0,
            'mutations_made': 0,
            'next_gate': 'adapter-failure-recovery',
            'reply': 'Adapter-Ergebnis konnte nicht verifiziert werden. Keine weitere Zustandsaenderung wurde ausgefuehrt.',
        }

    verification_receipt = {
        'approval_id': str(item.id),
        'verified_by': payload.actor,
        'session_id': payload.session_id,
        'workspace_id': payload.workspace_id,
        'operator_id': payload.operator_id,
        'adapter': payload.dispatch_receipt.get('adapter'),
        'execution_domain': payload.dispatch_receipt.get('execution_domain'),
        'dispatch_verified': True,
        'adapter_result_verified': True,
        'adapter_reference': payload.adapter_result.get('reference'),
    }
    return {
        'state': 'adapter-result-verified',
        'approval_id': str(item.id),
        **verification,
        'verification_receipt': verification_receipt,
        'external_calls_made': 0,
        'mutations_made': 0,
        'next_gate': 'downstream-state-commit',
        'reply': 'Adapter-Ergebnis verifiziert. Downstream-State bleibt bis zum naechsten Gate unveraendert.',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_adapter_call_dispatch_v21_273 import command_center as v21_273_command_center

    html = v21_273_command_center()
    html = html.replace('v21.273', 'v21.274')
    html = html.replace(
        'AURON ADAPTER CALL DISPATCH COMMAND CENTER',
        'AURON ADAPTER RESULT VERIFICATION COMMAND CENTER',
    )
    return html
