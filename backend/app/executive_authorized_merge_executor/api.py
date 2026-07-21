from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from .models import (
    AuthorizedMergeAudit,
    AuthorizedMergeCreate,
    AuthorizedMergeRecord,
    AuthorizedMergeStatus,
    MergeExecutionRequest,
)
from .service import authorized_merge_executor_service

router = APIRouter(prefix="/v1/executive-authorized-merge-executor", tags=["executive-authorized-merge-executor"])


@router.get("/status", response_model=AuthorizedMergeStatus)
def status(workspace_id: str = Query(..., min_length=1)):
    return authorized_merge_executor_service.status(workspace_id)


@router.post("/executions", response_model=AuthorizedMergeRecord)
def create_execution(payload: AuthorizedMergeCreate):
    try:
        return authorized_merge_executor_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/executions", response_model=list[AuthorizedMergeRecord])
def list_executions(workspace_id: str = Query(..., min_length=1)):
    return authorized_merge_executor_service.list_records(workspace_id)


@router.get("/executions/{record_id}", response_model=AuthorizedMergeRecord)
def get_execution(record_id: UUID, workspace_id: str = Query(..., min_length=1)):
    record = authorized_merge_executor_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="merge execution record not found")
    return record


@router.post("/executions/{record_id}/execute", response_model=AuthorizedMergeRecord)
def execute(record_id: UUID, request: MergeExecutionRequest, workspace_id: str = Query(..., min_length=1)):
    try:
        return authorized_merge_executor_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuthorizedMergeAudit])
def audit(workspace_id: str = Query(..., min_length=1)):
    return authorized_merge_executor_service.audit_records(workspace_id)
