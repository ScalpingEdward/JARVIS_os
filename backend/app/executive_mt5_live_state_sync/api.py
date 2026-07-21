from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import LiveSyncAudit, LiveSyncCreate, LiveSyncExecuteRequest, LiveSyncRecord, LiveSyncStatus
from .service import live_state_sync_service

router = APIRouter(tags=["executive-mt5-live-state-sync"])


@router.get("/v1/executive-mt5-live-sync/status", response_model=LiveSyncStatus)
def get_status(workspace_id: str = Query(min_length=1, max_length=100)) -> LiveSyncStatus:
    return live_state_sync_service.status(workspace_id)


@router.post("/v1/executive-mt5-live-sync/synchronizations", response_model=LiveSyncRecord, status_code=status.HTTP_201_CREATED)
def create_synchronization(payload: LiveSyncCreate) -> LiveSyncRecord:
    try:
        return live_state_sync_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-live-sync/synchronizations", response_model=list[LiveSyncRecord])
def list_synchronizations(workspace_id: str = Query(min_length=1, max_length=100)) -> list[LiveSyncRecord]:
    return live_state_sync_service.list_records(workspace_id)


@router.get("/v1/executive-mt5-live-sync/synchronizations/{record_id}", response_model=LiveSyncRecord)
def get_synchronization(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> LiveSyncRecord:
    record = live_state_sync_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Live synchronization record not found")
    return record


@router.post("/v1/executive-mt5-live-sync/synchronizations/{record_id}/execute", response_model=LiveSyncRecord)
def execute_synchronization(record_id: UUID, request: LiveSyncExecuteRequest, workspace_id: str = Query(min_length=1, max_length=100)) -> LiveSyncRecord:
    try:
        return live_state_sync_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-live-sync/audit", response_model=list[LiveSyncAudit])
def get_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[LiveSyncAudit]:
    return live_state_sync_service.audit_records(workspace_id)
