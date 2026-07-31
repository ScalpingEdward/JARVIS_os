from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.approvals.models import ApprovalStatus
from app.approvals.service import approval_service

router = APIRouter(prefix='/auron/demo1/v21.264', tags=['auron-demo1-execution-adapter-selection'])


class AdapterSelectionRequest(BaseModel):
    approval_id: UUID
    actor: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)


def _scope_matches(item, payload: AdapterSelectionRequest) -> bool:
    return (
        item.arguments.get('session_id') == payload.session_id
        and item.arguments.get('workspace_id') == payload.workspace_id
        and item.requested_by == payload.operator_id
    )


def _adapter_for(action: str) -> dict:
    lowered = action.lower()
    if any(token in lowered for token in ('mt5', 'trade', 'financial')):
        return {
            'adapter': 'mt5-protected-adapter',
            'execution_domain': 'financial',
            'requires_secondary_gate': True,
        }
    if any(token in lowered for token in ('github', 'repository', 'pull_request', 'pull-request')):
        return {
            'adapter': 'github-remote-adapter',
            'execution_domain': 'code-remote',
            'requires_secondary_gate': True,
        }
    if any(token in lowered for token in ('shell', 'powershell', 'terminal', 'command')):
        return {
            'adapter': 'local-command-adapter',
            'execution_domain': 'local-system',
            'requires_secondary_gate': True,
        }
    if any(token in lowered for token in ('connector', 'email', 'calendar', 'gmail')):
        return {
            'adapter': 'connector-adapter',
            'execution_domain': 'connected-service',
            'requires_secondary_gate': True,
        }
    return {
        'adapter': 'governed-tool-adapter',
        'execution_domain': 'general',
        'requires_secondary_gate': True,
    }


@router.get('/adapter-status/{approval_id}')
def adapter_status(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    selected = _adapter_for(item.action)
    return {
        'approval_id': str(item.id),
        'approval_status': item.status.value,
        'dispatch_ready': item.status == ApprovalStatus.consumed,
        **selected,
        'adapter_invoked': False,
        'execution_performed': False,
    }


@router.post('/select-adapter')
def select_adapter(payload: AdapterSelectionRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    if item.status != ApprovalStatus.consumed:
        raise HTTPException(status_code=409, detail='Execution dispatch is not authorized')

    selected = _adapter_for(item.action)
    return {
        'state': 'adapter-selected',
        'approval_id': str(item.id),
        'actor': payload.actor,
        'action': item.action,
        'command': item.arguments.get('command'),
        **selected,
        'adapter_invoked': False,
        'execution_performed': False,
        'next_gate': 'adapter-preflight',
        'reply': 'Ausführungsadapter wurde ausgewählt. Der Adapter wurde noch nicht aufgerufen.',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    # Lazy import preserves the anti-circular-import isolation protocol.
    from app.api.routes.auron_demo1_execution_dispatch_gate_v21_263 import command_center as v21_263_command_center

    html = v21_263_command_center()
    html = html.replace('v21.263', 'v21.264')
    html = html.replace(
        'AURON EXECUTION DISPATCH GATE COMMAND CENTER',
        'AURON EXECUTION ADAPTER SELECTION COMMAND CENTER',
    )
    return html
