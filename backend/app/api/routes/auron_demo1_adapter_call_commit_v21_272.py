from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.approvals.models import ApprovalStatus
from app.approvals.service import approval_service

router = APIRouter(prefix='/auron/demo1/v21.272', tags=['auron-demo1-adapter-call-commit'])


class AdapterCallCommitRequest(BaseModel):
    approval_id: UUID
    actor: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    invocation_receipt: dict
    commit: bool = True
    emergency_stop_clear: bool = True
    runtime_healthy: bool = True
    adapter_ready: bool = True
    credentials_valid: bool = True
    policy_still_valid: bool = True


def _scope_matches(item, payload: AdapterCallCommitRequest) -> bool:
    return (
        item.arguments.get('session_id') == payload.session_id
        and item.arguments.get('workspace_id') == payload.workspace_id
        and item.requested_by == payload.operator_id
    )


def _validate_invocation_receipt(item, payload: AdapterCallCommitRequest) -> list[str]:
    receipt = payload.invocation_receipt
    blockers: list[str] = []
    if receipt.get('approval_id') != str(item.id):
        blockers.append('approval_id')
    if receipt.get('session_id') != payload.session_id:
        blockers.append('session_id')
    if receipt.get('workspace_id') != payload.workspace_id:
        blockers.append('workspace_id')
    if receipt.get('operator_id') != payload.operator_id:
        blockers.append('operator_id')
    if receipt.get('single_use_authorization_consumed') is not True:
        blockers.append('single_use_authorization_consumed')
    if receipt.get('runtime_checks_passed') is not True:
        blockers.append('runtime_checks_passed')
    if receipt.get('invocation_prepared') is not True:
        blockers.append('invocation_prepared')
    if not receipt.get('adapter'):
        blockers.append('adapter')
    if not receipt.get('execution_domain'):
        blockers.append('execution_domain')
    return blockers


def _commit_checks(payload: AdapterCallCommitRequest) -> dict:
    checks = {
        'emergency_stop_clear': payload.emergency_stop_clear,
        'runtime_healthy': payload.runtime_healthy,
        'adapter_ready': payload.adapter_ready,
        'credentials_valid': payload.credentials_valid,
        'policy_still_valid': payload.policy_still_valid,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {'checks': checks, 'blockers': blockers, 'ready': not blockers}


@router.get('/commit-status/{approval_id}')
def commit_status(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    return {
        'approval_id': str(item.id),
        'approval_status': item.status.value,
        'commit_available': item.status == ApprovalStatus.consumed,
        'adapter_invoked': False,
        'execution_performed': False,
        'external_calls_made': 0,
        'mutations_made': 0,
        'next_gate': 'adapter-call-commit',
    }


@router.post('/commit')
def commit_adapter_call(payload: AdapterCallCommitRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    if item.status != ApprovalStatus.consumed:
        raise HTTPException(status_code=409, detail='Adapter call commit is not authorized')

    receipt_blockers = _validate_invocation_receipt(item, payload)
    if receipt_blockers:
        return {
            'state': 'adapter-call-commit-blocked',
            'approval_id': str(item.id),
            'blockers': receipt_blockers,
            'adapter_invoked': False,
            'execution_performed': False,
            'external_calls_made': 0,
            'mutations_made': 0,
            'next_gate': 'controlled-adapter-boundary',
        }

    if payload.commit is not True:
        return {
            'state': 'adapter-call-commit-declined',
            'approval_id': str(item.id),
            'adapter_invoked': False,
            'execution_performed': False,
            'external_calls_made': 0,
            'mutations_made': 0,
            'next_gate': 'controlled-adapter-boundary',
            'reply': 'Adapter Call Commit wurde abgelehnt. Kein externer Aufruf wurde ausgefuehrt.',
        }

    readiness = _commit_checks(payload)
    if not readiness['ready']:
        return {
            'state': 'adapter-call-commit-blocked',
            'approval_id': str(item.id),
            **readiness,
            'adapter_invoked': False,
            'execution_performed': False,
            'external_calls_made': 0,
            'mutations_made': 0,
            'next_gate': 'preflight-remediation',
        }

    commit_receipt = {
        'approval_id': str(item.id),
        'committed_by': payload.actor,
        'session_id': payload.session_id,
        'workspace_id': payload.workspace_id,
        'operator_id': payload.operator_id,
        'adapter': payload.invocation_receipt.get('adapter'),
        'execution_domain': payload.invocation_receipt.get('execution_domain'),
        'single_use_authorization_consumed': True,
        'runtime_checks_passed': True,
        'invocation_prepared': True,
        'call_committed': True,
    }
    return {
        'state': 'adapter-call-committed',
        'approval_id': str(item.id),
        **readiness,
        'commit_receipt': commit_receipt,
        'adapter_invoked': False,
        'execution_performed': False,
        'external_calls_made': 0,
        'mutations_made': 0,
        'next_gate': 'adapter-call-dispatch',
        'reply': 'Adapter-Aufruf wurde final committed. Der externe Dispatch selbst wurde noch nicht ausgefuehrt.',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_controlled_adapter_boundary_v21_271 import command_center as v21_271_command_center

    html = v21_271_command_center()
    html = html.replace('v21.271', 'v21.272')
    html = html.replace(
        'AURON CONTROLLED ADAPTER BOUNDARY COMMAND CENTER',
        'AURON ADAPTER CALL COMMIT COMMAND CENTER',
    )
    return html
