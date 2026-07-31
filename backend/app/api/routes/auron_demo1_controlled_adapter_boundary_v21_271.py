from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.approvals.models import ApprovalStatus
from app.approvals.service import approval_service

router = APIRouter(prefix='/auron/demo1/v21.271', tags=['auron-demo1-controlled-adapter-boundary'])


class ControlledAdapterBoundaryRequest(BaseModel):
    approval_id: UUID
    actor: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    authorization_receipt: dict
    emergency_stop_clear: bool = True
    runtime_healthy: bool = True
    adapter_ready: bool = True
    credentials_valid: bool = True
    policy_still_valid: bool = True


def _scope_matches(item, payload: ControlledAdapterBoundaryRequest) -> bool:
    return (
        item.arguments.get('session_id') == payload.session_id
        and item.arguments.get('workspace_id') == payload.workspace_id
        and item.requested_by == payload.operator_id
    )


def _validate_authorization(item, payload: ControlledAdapterBoundaryRequest) -> list[str]:
    receipt = payload.authorization_receipt
    blockers: list[str] = []
    if receipt.get('approval_id') != str(item.id):
        blockers.append('approval_id')
    if receipt.get('session_id') != payload.session_id:
        blockers.append('session_id')
    if receipt.get('workspace_id') != payload.workspace_id:
        blockers.append('workspace_id')
    if receipt.get('operator_id') != payload.operator_id:
        blockers.append('operator_id')
    if receipt.get('token_consumed') is not True:
        blockers.append('token_consumed')
    if receipt.get('single_use_enforced') is not True:
        blockers.append('single_use_enforced')
    if not receipt.get('adapter'):
        blockers.append('adapter')
    if not receipt.get('execution_domain'):
        blockers.append('execution_domain')
    return blockers


def _runtime_checks(payload: ControlledAdapterBoundaryRequest) -> dict:
    checks = {
        'emergency_stop_clear': payload.emergency_stop_clear,
        'runtime_healthy': payload.runtime_healthy,
        'adapter_ready': payload.adapter_ready,
        'credentials_valid': payload.credentials_valid,
        'policy_still_valid': payload.policy_still_valid,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {'checks': checks, 'blockers': blockers, 'ready': not blockers}


@router.get('/boundary-status/{approval_id}')
def boundary_status(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    return {
        'approval_id': str(item.id),
        'approval_status': item.status.value,
        'boundary_available': item.status == ApprovalStatus.consumed,
        'adapter_invoked': False,
        'execution_performed': False,
        'next_gate': 'controlled-adapter-boundary',
    }


@router.post('/prepare-invocation')
def prepare_invocation(payload: ControlledAdapterBoundaryRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    if item.status != ApprovalStatus.consumed:
        raise HTTPException(status_code=409, detail='Controlled adapter boundary is not authorized')

    auth_blockers = _validate_authorization(item, payload)
    if auth_blockers:
        return {
            'state': 'adapter-boundary-blocked',
            'approval_id': str(item.id),
            'blockers': auth_blockers,
            'adapter_invoked': False,
            'execution_performed': False,
            'next_gate': 'one-shot-authorization',
        }

    readiness = _runtime_checks(payload)
    if not readiness['ready']:
        return {
            'state': 'adapter-boundary-blocked',
            'approval_id': str(item.id),
            **readiness,
            'adapter_invoked': False,
            'execution_performed': False,
            'next_gate': 'preflight-remediation',
        }

    invocation_receipt = {
        'approval_id': str(item.id),
        'prepared_by': payload.actor,
        'session_id': payload.session_id,
        'workspace_id': payload.workspace_id,
        'operator_id': payload.operator_id,
        'adapter': payload.authorization_receipt.get('adapter'),
        'execution_domain': payload.authorization_receipt.get('execution_domain'),
        'single_use_authorization_consumed': True,
        'runtime_checks_passed': True,
        'invocation_prepared': True,
    }
    return {
        'state': 'adapter-invocation-prepared',
        'approval_id': str(item.id),
        **readiness,
        'invocation_receipt': invocation_receipt,
        'adapter_invoked': False,
        'execution_performed': False,
        'external_calls_made': 0,
        'mutations_made': 0,
        'next_gate': 'adapter-call-commit',
        'reply': 'Adapter-Aufruf ist vorbereitet und freigegeben. Noch wurde kein externer Aufruf ausgefuehrt.',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_single_use_execution_token_v21_270 import command_center as v21_270_command_center

    html = v21_270_command_center()
    html = html.replace('v21.270', 'v21.271')
    html = html.replace(
        'AURON SINGLE-USE EXECUTION TOKEN COMMAND CENTER',
        'AURON CONTROLLED ADAPTER BOUNDARY COMMAND CENTER',
    )
    return html
