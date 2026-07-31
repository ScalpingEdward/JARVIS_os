from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.approvals.models import ApprovalStatus
from app.approvals.service import approval_service

v21_269_router = APIRouter(prefix='/auron/demo1/v21.269', tags=['auron-demo1-live-execution-arm-gate'])


class LiveExecutionArmRequest(BaseModel):
    approval_id: UUID
    actor: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    confirmation_receipt: dict
    arm: bool = True
    emergency_stop_clear: bool = True
    runtime_healthy: bool = True
    adapter_ready: bool = True
    credentials_valid: bool = True
    policy_still_valid: bool = True


def _scope_matches(item, payload: LiveExecutionArmRequest) -> bool:
    return (
        item.arguments.get('session_id') == payload.session_id
        and item.arguments.get('workspace_id') == payload.workspace_id
        and item.requested_by == payload.operator_id
    )


def _validate_confirmation(item, payload: LiveExecutionArmRequest) -> list[str]:
    receipt = payload.confirmation_receipt
    blockers: list[str] = []
    if receipt.get('approval_id') != str(item.id):
        blockers.append('approval_id')
    if receipt.get('session_id') != payload.session_id:
        blockers.append('session_id')
    if receipt.get('workspace_id') != payload.workspace_id:
        blockers.append('workspace_id')
    if receipt.get('operator_id') != payload.operator_id:
        blockers.append('operator_id')
    if receipt.get('operator_confirmed') is not True:
        blockers.append('operator_confirmed')
    if not receipt.get('preview_adapter'):
        blockers.append('preview_adapter')
    if not receipt.get('execution_domain'):
        blockers.append('execution_domain')
    return blockers


def _arm_readiness(payload: LiveExecutionArmRequest) -> dict:
    checks = {
        'emergency_stop_clear': payload.emergency_stop_clear,
        'runtime_healthy': payload.runtime_healthy,
        'adapter_ready': payload.adapter_ready,
        'credentials_valid': payload.credentials_valid,
        'policy_still_valid': payload.policy_still_valid,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {'checks': checks, 'blockers': blockers, 'ready': not blockers}


@v21_269_router.get('/arm-status/{approval_id}')
def arm_status(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    return {
        'approval_id': str(item.id),
        'approval_status': item.status.value,
        'arming_available': item.status == ApprovalStatus.consumed,
        'live_execution_enabled': False,
        'execution_performed': False,
        'next_gate': 'live-execution-arm-review',
    }


@v21_269_router.post('/arm')
def arm(payload: LiveExecutionArmRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    if item.status != ApprovalStatus.consumed:
        raise HTTPException(status_code=409, detail='Live execution arming is not authorized')

    receipt_blockers = _validate_confirmation(item, payload)
    if receipt_blockers:
        return {
            'state': 'arming-blocked',
            'approval_id': str(item.id),
            'blockers': receipt_blockers,
            'live_execution_enabled': False,
            'execution_performed': False,
            'next_gate': 'execution-preview-review',
            'reply': 'Live Execution Arm Gate blockiert: Confirmation Receipt ist ungueltig.',
        }

    if payload.arm is not True:
        return {
            'state': 'arming-declined',
            'approval_id': str(item.id),
            'live_execution_enabled': False,
            'execution_performed': False,
            'next_gate': 'execution-preview-review',
            'reply': 'Live-Ausfuehrung wurde nicht scharfgeschaltet.',
        }

    readiness = _arm_readiness(payload)
    if not readiness['ready']:
        return {
            'state': 'arming-blocked',
            'approval_id': str(item.id),
            **readiness,
            'live_execution_enabled': False,
            'execution_performed': False,
            'next_gate': 'preflight-remediation',
            'reply': 'Live Execution Arm Gate blockiert: Runtime- oder Sicherheitsvoraussetzungen fehlen.',
        }

    arm_receipt = {
        'approval_id': str(item.id),
        'armed_by': payload.actor,
        'session_id': payload.session_id,
        'workspace_id': payload.workspace_id,
        'operator_id': payload.operator_id,
        'adapter': payload.confirmation_receipt.get('preview_adapter'),
        'execution_domain': payload.confirmation_receipt.get('execution_domain'),
        'predicted_risk': payload.confirmation_receipt.get('predicted_risk'),
        'operator_confirmed': True,
        'safety_checks_passed': True,
        'armed': True,
    }
    return {
        'state': 'execution-armed',
        'approval_id': str(item.id),
        **readiness,
        'arm_receipt': arm_receipt,
        'live_execution_enabled': False,
        'adapter_invoked': False,
        'execution_performed': False,
        'next_gate': 'single-use-execution-token',
        'reply': 'Execution ist vorbereitet und scharfgeschaltet. Es wurde noch keine Live-Aktion ausgefuehrt.',
    }


@v21_269_router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_execution_preview_review_v21_268 import command_center as v21_268_command_center

    html = v21_268_command_center()
    html = html.replace('v21.268', 'v21.269')
    html = html.replace(
        'AURON EXECUTION PREVIEW REVIEW COMMAND CENTER',
        'AURON LIVE EXECUTION ARM GATE COMMAND CENTER',
    )
    return html


# Composite registration keeps app.main stable while exposing the next isolated gate.
from app.api.routes.auron_demo1_single_use_execution_token_v21_270 import router as v21_270_router

router = APIRouter()
router.include_router(v21_269_router)
router.include_router(v21_270_router)
