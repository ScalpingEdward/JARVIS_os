from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.approvals.models import ApprovalStatus
from app.approvals.service import ApprovalError, approval_service

router = APIRouter(prefix='/auron/demo1/v21.262', tags=['auron-demo1-approved-resume-gate'])


class ResumeAuthorizationRequest(BaseModel):
    approval_id: UUID
    confirmation_token: str = Field(min_length=1)
    actor: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)


def _scope_matches(item, payload: ResumeAuthorizationRequest) -> bool:
    return (
        item.arguments.get('session_id') == payload.session_id
        and item.arguments.get('workspace_id') == payload.workspace_id
        and item.requested_by == payload.operator_id
    )


@router.get('/resume-status/{approval_id}')
def resume_status(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    return {
        'approval_id': str(item.id),
        'status': item.status.value,
        'resume_ready': item.status == ApprovalStatus.approved,
        'resume_consumed': item.status == ApprovalStatus.consumed,
        'execution_performed': False,
    }


@router.post('/authorize-resume')
def authorize_resume(payload: ResumeAuthorizationRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    if item.status != ApprovalStatus.approved:
        raise HTTPException(status_code=409, detail='Approval is not resume-ready')

    try:
        consumed = approval_service.consume(payload.approval_id, payload.confirmation_token, payload.actor)
    except ApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        'state': 'resume-authorized',
        'approval_id': str(consumed.id),
        'status': consumed.status.value,
        'resume_authorized': True,
        'execution_performed': False,
        'next_gate': 'execution-dispatch',
        'reply': 'Freigabe bestätigt und einmalig konsumiert. Ausführung wurde noch nicht gestartet.',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    # Lazy import keeps v21.262 isolated from the historical AURON route chain at startup.
    from app.api.routes.auron_demo1_approval_resolution_v21_261 import command_center as v21_261_command_center

    html = v21_261_command_center()
    html = html.replace('v21.261', 'v21.262')
    html = html.replace(
        'AURON APPROVAL RESOLUTION COMMAND CENTER',
        'AURON APPROVED RESUME GATE COMMAND CENTER',
    )
    return html
