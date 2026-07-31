from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.approvals.models import ApprovalStatus
from app.approvals.service import approval_service

v21_268_router = APIRouter(prefix='/auron/demo1/v21.268', tags=['auron-demo1-execution-preview-review'])


class ExecutionPreviewReviewRequest(BaseModel):
    approval_id: UUID
    actor: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    preview_receipt: dict
    decision: str = Field(pattern='^(confirm|reject)$')
    note: str | None = Field(default=None, max_length=500)


def _scope_matches(item, payload: ExecutionPreviewReviewRequest) -> bool:
    return (
        item.arguments.get('session_id') == payload.session_id
        and item.arguments.get('workspace_id') == payload.workspace_id
        and item.requested_by == payload.operator_id
    )


def _validate_receipt(item, payload: ExecutionPreviewReviewRequest) -> list[str]:
    receipt = payload.preview_receipt
    blockers: list[str] = []
    if receipt.get('approval_id') != str(item.id):
        blockers.append('approval_id')
    if receipt.get('session_id') != payload.session_id:
        blockers.append('session_id')
    if receipt.get('workspace_id') != payload.workspace_id:
        blockers.append('workspace_id')
    if receipt.get('operator_id') != payload.operator_id:
        blockers.append('operator_id')
    if receipt.get('mode') != 'dry-run':
        blockers.append('mode')
    if receipt.get('external_calls_made') != 0:
        blockers.append('external_calls_made')
    if receipt.get('mutations_made') != 0:
        blockers.append('mutations_made')
    return blockers


@v21_268_router.get('/review-status/{approval_id}')
def review_status(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    return {
        'approval_id': str(item.id),
        'approval_status': item.status.value,
        'review_available': item.status == ApprovalStatus.consumed,
        'execution_performed': False,
        'next_gate': 'operator-preview-confirmation',
    }


@v21_268_router.post('/review')
def review(payload: ExecutionPreviewReviewRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    if item.status != ApprovalStatus.consumed:
        raise HTTPException(status_code=409, detail='Execution preview review is not authorized')

    blockers = _validate_receipt(item, payload)
    if blockers:
        return {
            'state': 'preview-review-blocked',
            'approval_id': str(item.id),
            'blockers': blockers,
            'execution_performed': False,
            'next_gate': 'dry-run-simulation',
            'reply': 'Execution Preview Review blockiert: Preview Receipt ist ungueltig oder passt nicht zum Scope.',
        }

    if payload.decision == 'reject':
        return {
            'state': 'preview-rejected',
            'approval_id': str(item.id),
            'confirmed_by': payload.actor,
            'note': payload.note,
            'execution_performed': False,
            'next_gate': 'execution-plan-revision',
            'reply': 'Execution Preview abgelehnt. Keine Ausfuehrung wurde gestartet.',
        }

    confirmation_receipt = {
        'approval_id': str(item.id),
        'confirmed_by': payload.actor,
        'session_id': payload.session_id,
        'workspace_id': payload.workspace_id,
        'operator_id': payload.operator_id,
        'preview_adapter': payload.preview_receipt.get('adapter'),
        'execution_domain': payload.preview_receipt.get('execution_domain'),
        'predicted_risk': payload.preview_receipt.get('predicted_risk'),
        'note': payload.note,
        'operator_confirmed': True,
    }
    return {
        'state': 'preview-confirmed',
        'approval_id': str(item.id),
        'confirmation_receipt': confirmation_receipt,
        'execution_performed': False,
        'adapter_invoked': False,
        'next_gate': 'live-execution-arm-gate',
        'reply': 'Execution Preview bestaetigt. Live-Ausfuehrung bleibt gesperrt bis zum naechsten Gate.',
    }


@v21_268_router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_adapter_dry_run_simulation_v21_267 import command_center as v21_267_command_center

    html = v21_267_command_center()
    html = html.replace('v21.267', 'v21.268')
    html = html.replace(
        'AURON ADAPTER DRY-RUN SIMULATION COMMAND CENTER',
        'AURON EXECUTION PREVIEW REVIEW COMMAND CENTER',
    )
    return html


# Composite registration keeps app.main unchanged while exposing the next isolated gate.
from app.api.routes.auron_demo1_live_execution_arm_gate_v21_269 import router as v21_269_router

router = APIRouter()
router.include_router(v21_268_router)
router.include_router(v21_269_router)
