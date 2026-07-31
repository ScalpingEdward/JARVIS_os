from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.approvals.models import ApprovalStatus
from app.approvals.service import approval_service

router = APIRouter(prefix='/auron/demo1/v21.261', tags=['auron-demo1-approval-resolution'])


def _serialize(item) -> dict:
    return {
        'approval_id': str(item.id),
        'status': item.status.value,
        'action': item.action,
        'command': item.arguments.get('command'),
        'session_id': item.arguments.get('session_id'),
        'workspace_id': item.arguments.get('workspace_id'),
        'requested_by': item.requested_by,
        'approved_by': item.approved_by,
        'rejected_by': item.rejected_by,
        'decided_at': item.decided_at.isoformat() if item.decided_at else None,
        'resume_ready': item.status == ApprovalStatus.approved,
        'terminal': item.status in {ApprovalStatus.rejected, ApprovalStatus.consumed},
    }


def _matches(item, session_id: str, workspace_id: str, operator_id: str) -> bool:
    return (
        item.arguments.get('session_id') == session_id
        and item.arguments.get('workspace_id') == workspace_id
        and item.requested_by == operator_id
    )


@router.get('/resolution-status')
def resolution_status(
    session_id: str = 'approval',
    workspace_id: str = 'demo',
    operator_id: str = 'brano',
) -> dict:
    items = [
        _serialize(item)
        for item in approval_service.list()
        if _matches(item, session_id, workspace_id, operator_id)
    ]
    return {
        'count': len(items),
        'pending': sum(item['status'] == ApprovalStatus.pending.value for item in items),
        'approved': sum(item['status'] == ApprovalStatus.approved.value for item in items),
        'rejected': sum(item['status'] == ApprovalStatus.rejected.value for item in items),
        'consumed': sum(item['status'] == ApprovalStatus.consumed.value for item in items),
        'resume_ready': any(item['resume_ready'] for item in items),
        'items': items,
    }


@router.get('/resolution/{approval_id}')
def resolution(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    return _serialize(item)


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    # Lazy import is intentional: never reconnect the historical AURON router chain
    # during module import / pytest collection.
    from app.api.routes.auron_demo1_approval_handoff_v21_260 import command_center as v21_260_command_center

    html = v21_260_command_center()
    html = html.replace('v21.260', 'v21.261')
    html = html.replace(
        'AURON APPROVAL HANDOFF COMMAND CENTER',
        'AURON APPROVAL RESOLUTION COMMAND CENTER',
    )
    return html
