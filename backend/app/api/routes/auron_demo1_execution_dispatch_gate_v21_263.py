from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.approvals.models import ApprovalStatus
from app.approvals.service import approval_service

router = APIRouter(prefix='/auron/demo1/v21.263', tags=['auron-demo1-execution-dispatch-gate'])


class DispatchRequest(BaseModel):
    approval_id: UUID
    actor: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)


def _scope_matches(item, payload: DispatchRequest) -> bool:
    return (
        item.arguments.get('session_id') == payload.session_id
        and item.arguments.get('workspace_id') == payload.workspace_id
        and item.requested_by == payload.operator_id
    )


def _dispatch_class(action: str) -> str:
    lowered = action.lower()
    if any(token in lowered for token in ('trade', 'mt5', 'financial')):
        return 'financial-protected'
    if any(token in lowered for token in ('github', 'deploy', 'remote')):
        return 'remote-protected'
    return 'governed-action'


@router.get('/dispatch-status/{approval_id}')
def dispatch_status(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    return {
        'approval_id': str(item.id),
        'approval_status': item.status.value,
        'resume_authorized': item.status == ApprovalStatus.consumed,
        'dispatch_ready': item.status == ApprovalStatus.consumed,
        'dispatch_class': _dispatch_class(item.action),
        'execution_performed': False,
    }


@router.post('/prepare-dispatch')
def prepare_dispatch(payload: DispatchRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    if item.status != ApprovalStatus.consumed:
        raise HTTPException(status_code=409, detail='Resume authorization has not been consumed')

    dispatch_class = _dispatch_class(item.action)
    return {
        'state': 'dispatch-prepared',
        'approval_id': str(item.id),
        'actor': payload.actor,
        'action': item.action,
        'command': item.arguments.get('command'),
        'dispatch_class': dispatch_class,
        'dispatch_ready': True,
        'execution_performed': False,
        'next_gate': 'execution-adapter-selection',
        'reply': 'Ausführung ist für Dispatch vorbereitet. Noch wurde kein Tool und keine externe Aktion gestartet.',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    # Lazy import preserves the anti-circular-import isolation protocol.
    from app.api.routes.auron_demo1_approved_resume_gate_v21_262 import command_center as v21_262_command_center

    html = v21_262_command_center()
    html = html.replace('v21.262', 'v21.263')
    html = html.replace(
        'AURON APPROVED RESUME GATE COMMAND CENTER',
        'AURON EXECUTION DISPATCH GATE COMMAND CENTER',
    )
    return html
