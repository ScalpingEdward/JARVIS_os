from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.approvals.models import ApprovalStatus
from app.approvals.service import approval_service

router = APIRouter(prefix='/auron/demo1/v21.267', tags=['auron-demo1-adapter-dry-run-simulation'])


class DryRunSimulationRequest(BaseModel):
    approval_id: UUID
    actor: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    adapter_registered: bool = True
    runtime_available: bool = True
    credentials_present: bool = True
    operator_enabled: bool = True
    dry_run: bool = True


def _scope_matches(item, payload: DryRunSimulationRequest) -> bool:
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


def _readiness(selected: dict, payload: DryRunSimulationRequest) -> dict:
    checks = {
        'adapter_registered': payload.adapter_registered,
        'runtime_available': payload.runtime_available,
        'operator_enabled': payload.operator_enabled,
        'credentials_present': payload.credentials_present if selected['credentials_required'] else True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {'checks': checks, 'blockers': blockers, 'ready': not blockers}


def _preview_for(selected: dict, action: str, command: str | None) -> dict:
    domain = selected['execution_domain']
    if domain == 'financial':
        effects = ['validate-order-payload', 'resolve-symbol', 'estimate-order-request']
        risk = 'high'
    elif domain == 'code-remote':
        effects = ['resolve-repository-target', 'preview-remote-mutation', 'estimate-api-request']
        risk = 'high'
    elif domain == 'local-system':
        effects = ['parse-command', 'preview-process-launch', 'estimate-local-side-effects']
        risk = 'high'
    elif domain == 'connected-service':
        effects = ['resolve-connector-target', 'preview-service-request', 'estimate-remote-side-effects']
        risk = 'high'
    else:
        effects = ['resolve-tool-target', 'preview-tool-input', 'estimate-tool-side-effects']
        risk = 'medium'
    return {
        'action': action,
        'command': command,
        'simulated_steps': effects,
        'predicted_risk': risk,
        'external_calls_made': 0,
        'mutations_made': 0,
    }


@router.get('/simulation-status/{approval_id}')
def simulation_status(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    selected = _adapter_for(item.action)
    return {
        'approval_id': str(item.id),
        'approval_status': item.status.value,
        **selected,
        'simulation_mode': 'dry-run-only',
        'simulation_available': item.status == ApprovalStatus.consumed,
        'adapter_invoked': False,
        'execution_performed': False,
    }


@router.post('/simulate')
def simulate(payload: DryRunSimulationRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    if item.status != ApprovalStatus.consumed:
        raise HTTPException(status_code=409, detail='Dry-run simulation is not authorized')
    if payload.dry_run is not True:
        raise HTTPException(status_code=409, detail='Live execution is disabled in v21.267')

    selected = _adapter_for(item.action)
    readiness = _readiness(selected, payload)
    if not readiness['ready']:
        return {
            'state': 'simulation-blocked',
            'approval_id': str(item.id),
            **selected,
            **readiness,
            'adapter_invoked': False,
            'execution_performed': False,
            'next_gate': 'preflight-remediation',
            'reply': 'Dry-Run-Simulation blockiert: Voraussetzungen fehlen.',
        }

    preview = _preview_for(selected, item.action, item.arguments.get('command'))
    receipt = {
        'approval_id': str(item.id),
        'actor': payload.actor,
        'session_id': payload.session_id,
        'workspace_id': payload.workspace_id,
        'operator_id': payload.operator_id,
        'adapter': selected['adapter'],
        'execution_domain': selected['execution_domain'],
        'mode': 'dry-run',
        **preview,
    }
    return {
        'state': 'simulation-complete',
        **selected,
        **readiness,
        'preview_receipt': receipt,
        'adapter_invoked': False,
        'execution_performed': False,
        'next_gate': 'execution-preview-review',
        'reply': 'Dry-Run-Simulation abgeschlossen. Es wurden keine externen Aufrufe oder Änderungen ausgeführt.',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    # Lazy import preserves the anti-circular-import isolation protocol.
    from app.api.routes.auron_demo1_controlled_adapter_invocation_v21_266 import command_center as v21_266_command_center

    html = v21_266_command_center()
    html = html.replace('v21.266', 'v21.267')
    html = html.replace(
        'AURON CONTROLLED ADAPTER INVOCATION COMMAND CENTER',
        'AURON ADAPTER DRY-RUN SIMULATION COMMAND CENTER',
    )
    return html
