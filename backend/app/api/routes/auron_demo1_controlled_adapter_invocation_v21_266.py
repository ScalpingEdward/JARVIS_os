from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.approvals.models import ApprovalStatus
from app.approvals.service import approval_service

router = APIRouter(prefix='/auron/demo1/v21.266', tags=['auron-demo1-controlled-adapter-invocation'])


class ControlledInvocationRequest(BaseModel):
    approval_id: UUID
    actor: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    adapter_registered: bool = False
    runtime_available: bool = False
    credentials_present: bool = False
    operator_enabled: bool = False
    dry_run: bool = True


def _scope_matches(item, payload: ControlledInvocationRequest) -> bool:
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


def _preflight(selected: dict, payload: ControlledInvocationRequest) -> dict:
    checks = {
        'adapter_registered': payload.adapter_registered,
        'runtime_available': payload.runtime_available,
        'operator_enabled': payload.operator_enabled,
        'credentials_present': payload.credentials_present if selected['credentials_required'] else True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {'checks': checks, 'blockers': blockers, 'preflight_passed': not blockers}


@router.get('/invocation-status/{approval_id}')
def invocation_status(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    selected = _adapter_for(item.action)
    return {
        'approval_id': str(item.id),
        'approval_status': item.status.value,
        'resume_authorized': item.status == ApprovalStatus.consumed,
        **selected,
        'invocation_mode': 'dry-run-only',
        'adapter_invoked': False,
        'execution_performed': False,
    }


@router.post('/prepare-invocation')
def prepare_invocation(payload: ControlledInvocationRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    if item.status != ApprovalStatus.consumed:
        raise HTTPException(status_code=409, detail='Controlled invocation is not authorized')
    if payload.dry_run is not True:
        raise HTTPException(status_code=409, detail='Live adapter invocation is not enabled in v21.266')

    selected = _adapter_for(item.action)
    preflight = _preflight(selected, payload)
    if not preflight['preflight_passed']:
        return {
            'state': 'invocation-blocked',
            'approval_id': str(item.id),
            **selected,
            **preflight,
            'dry_run': True,
            'adapter_invoked': False,
            'execution_performed': False,
            'next_gate': 'preflight-remediation',
            'reply': 'Kontrollierter Adapter-Aufruf blockiert: Preflight-Voraussetzungen fehlen.',
        }

    envelope = {
        'approval_id': str(item.id),
        'actor': payload.actor,
        'action': item.action,
        'command': item.arguments.get('command'),
        'session_id': payload.session_id,
        'workspace_id': payload.workspace_id,
        'operator_id': payload.operator_id,
        'adapter': selected['adapter'],
        'execution_domain': selected['execution_domain'],
        'mode': 'dry-run',
    }
    return {
        'state': 'invocation-prepared',
        **selected,
        **preflight,
        'invocation_envelope': envelope,
        'dry_run': True,
        'adapter_invoked': False,
        'execution_performed': False,
        'next_gate': 'adapter-dry-run-simulation',
        'reply': 'Kontrollierter Adapter-Aufruf wurde als Dry-Run-Envelope vorbereitet. Der Adapter wurde nicht ausgeführt.',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    # Lazy import preserves the anti-circular-import isolation protocol.
    from app.api.routes.auron_demo1_adapter_preflight_readiness_v21_265 import command_center as v21_265_command_center

    html = v21_265_command_center()
    html = html.replace('v21.265', 'v21.266')
    html = html.replace(
        'AURON ADAPTER PREFLIGHT READINESS COMMAND CENTER',
        'AURON CONTROLLED ADAPTER INVOCATION COMMAND CENTER',
    )
    return html
