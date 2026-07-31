from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.approvals.models import ApprovalStatus
from app.approvals.service import approval_service

router = APIRouter(prefix='/auron/demo1/v21.265', tags=['auron-demo1-adapter-preflight-readiness'])


class AdapterPreflightRequest(BaseModel):
    approval_id: UUID
    actor: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    adapter_registered: bool = False
    runtime_available: bool = False
    credentials_present: bool = False
    operator_enabled: bool = False


def _scope_matches(item, payload: AdapterPreflightRequest) -> bool:
    return (
        item.arguments.get('session_id') == payload.session_id
        and item.arguments.get('workspace_id') == payload.workspace_id
        and item.requested_by == payload.operator_id
    )


def _adapter_for(action: str) -> dict:
    lowered = action.lower()
    if any(token in lowered for token in ('mt5', 'trade', 'financial')):
        return {'adapter': 'mt5-protected-adapter', 'execution_domain': 'financial', 'credentials_required': True}
    if any(token in lowered for token in ('github', 'repository', 'pull_request', 'pull-request')):
        return {'adapter': 'github-remote-adapter', 'execution_domain': 'code-remote', 'credentials_required': True}
    if any(token in lowered for token in ('shell', 'powershell', 'terminal', 'command')):
        return {'adapter': 'local-command-adapter', 'execution_domain': 'local-system', 'credentials_required': False}
    if any(token in lowered for token in ('connector', 'email', 'calendar', 'gmail')):
        return {'adapter': 'connector-adapter', 'execution_domain': 'connected-service', 'credentials_required': True}
    return {'adapter': 'governed-tool-adapter', 'execution_domain': 'general', 'credentials_required': False}


def _preflight(selected: dict, payload: AdapterPreflightRequest) -> dict:
    checks = {
        'adapter_registered': payload.adapter_registered,
        'runtime_available': payload.runtime_available,
        'operator_enabled': payload.operator_enabled,
        'credentials_present': payload.credentials_present if selected['credentials_required'] else True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {
        **selected,
        'checks': checks,
        'blockers': blockers,
        'preflight_passed': not blockers,
        'ready_for_invoke': not blockers,
        'adapter_invoked': False,
        'execution_performed': False,
    }


@router.get('/preflight-status/{approval_id}')
def preflight_status(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    selected = _adapter_for(item.action)
    return {
        'approval_id': str(item.id),
        'approval_status': item.status.value,
        'dispatch_authorized': item.status == ApprovalStatus.consumed,
        **selected,
        'evidence_required': ['adapter_registered', 'runtime_available', 'operator_enabled']
        + (['credentials_present'] if selected['credentials_required'] else []),
        'adapter_invoked': False,
        'execution_performed': False,
    }


@router.post('/run-preflight')
def run_preflight(payload: AdapterPreflightRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    if item.status != ApprovalStatus.consumed:
        raise HTTPException(status_code=409, detail='Adapter selection is not authorized')

    result = _preflight(_adapter_for(item.action), payload)
    return {
        'state': 'preflight-passed' if result['preflight_passed'] else 'preflight-blocked',
        'approval_id': str(item.id),
        'actor': payload.actor,
        'action': item.action,
        'command': item.arguments.get('command'),
        **result,
        'next_gate': 'controlled-adapter-invocation' if result['preflight_passed'] else 'preflight-remediation',
        'reply': 'Adapter-Preflight bestanden; kontrollierter Aufruf kann vorbereitet werden.'
        if result['preflight_passed']
        else 'Adapter-Preflight blockiert. Fehlende Voraussetzungen müssen zuerst erfüllt werden.',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    # Lazy import preserves the anti-circular-import isolation protocol.
    from app.api.routes.auron_demo1_execution_adapter_selection_v21_264 import command_center as v21_264_command_center

    html = v21_264_command_center()
    html = html.replace('v21.264', 'v21.265')
    html = html.replace(
        'AURON EXECUTION ADAPTER SELECTION COMMAND CENTER',
        'AURON ADAPTER PREFLIGHT READINESS COMMAND CENTER',
    )
    return html
