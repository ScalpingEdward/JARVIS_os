from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from .models import (
    MergeAuthorizationAudit,
    MergeAuthorizationCreate,
    MergeAuthorizationExecuteRequest,
    MergeAuthorizationRecord,
    MergeAuthorizationStatus,
)
from .service import human_merge_authorization_service

router = APIRouter(prefix="/v1/executive-human-merge-authorization", tags=["executive-human-merge-authorization"])


@router.get("/status", response_model=MergeAuthorizationStatus)
def status(workspace_id: str = Query(...)):
    return human_merge_authorization_service.status(workspace_id)


@router.post("/authorizations", response_model=MergeAuthorizationRecord)
def create_authorization(payload: MergeAuthorizationCreate):
    try:
        return human_merge_authorization_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/authorizations", response_model=list[MergeAuthorizationRecord])
def list_authorizations(workspace_id: str = Query(...)):
    return human_merge_authorization_service.list_records(workspace_id)


@router.get("/authorizations/{record_id}", response_model=MergeAuthorizationRecord)
def get_authorization(record_id: UUID, workspace_id: str = Query(...)):
    record = human_merge_authorization_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="merge authorization record not found")
    return record


@router.post("/authorizations/{record_id}/execute", response_model=MergeAuthorizationRecord)
def execute_authorization(record_id: UUID, request: MergeAuthorizationExecuteRequest, workspace_id: str = Query(...)):
    try:
        return human_merge_authorization_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[MergeAuthorizationAudit])
def audit(workspace_id: str = Query(...)):
    return human_merge_authorization_service.audit_records(workspace_id)
