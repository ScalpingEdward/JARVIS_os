from fastapi import APIRouter, HTTPException, Query

from app.schemas.phoenix_demo1_approval_inbox_v21_228 import (
    ApprovalInboxList,
    DeferredRecoveryRequest,
    DeferredRecoveryResult,
    InboxStatus,
    ApprovalInboxRecord,
)
from app.services.phoenix_demo1_approval_inbox_v21_228 import ApprovalInboxError, approval_inbox_service

router = APIRouter(prefix='/phoenix/demo1/v21.228/approvals', tags=['phoenix-demo1-v21.228'])


@router.get('/status', response_model=InboxStatus)
def status():
    return approval_inbox_service.status()


@router.get('', response_model=ApprovalInboxList)
def list_inbox(state: str | None = Query(default=None)):
    items = approval_inbox_service.list(state=state)
    return ApprovalInboxList(items=items, count=len(items))


@router.post('/recover-deferred', response_model=DeferredRecoveryResult)
def recover_deferred(req: DeferredRecoveryRequest):
    return approval_inbox_service.recover_deferred(req)


@router.post('/{approval_id}/resolve', response_model=ApprovalInboxRecord)
def resolve(approval_id: str):
    try:
        return approval_inbox_service.resolve(approval_id)
    except ApprovalInboxError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
