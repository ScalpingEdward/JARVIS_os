from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, OperationsListResponse, OperationsSnapshot, OperationsSnapshotCreate, OperationsStatus
from .service import executive_operations_service

router = APIRouter(tags=["executive-operations"])


@router.get("/v1/executive-operations/status", response_model=OperationsStatus)
def operations_status(workspace_id: str = Query(min_length=1, max_length=100)) -> OperationsStatus:
    return executive_operations_service.status(workspace_id)


@router.post("/v1/executive-operations/snapshots", response_model=OperationsSnapshot, status_code=status.HTTP_201_CREATED)
def create_snapshot(payload: OperationsSnapshotCreate) -> OperationsSnapshot:
    try:
        return executive_operations_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-operations/snapshots", response_model=OperationsListResponse)
def list_snapshots(workspace_id: str = Query(min_length=1, max_length=100)) -> OperationsListResponse:
    items = executive_operations_service.list_snapshots(workspace_id)
    return OperationsListResponse(items=items, count=len(items))


@router.get("/v1/executive-operations/snapshots/{snapshot_id}", response_model=OperationsSnapshot)
def get_snapshot(snapshot_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> OperationsSnapshot:
    record = executive_operations_service.get(snapshot_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Operations snapshot not found")
    return record


@router.post("/v1/executive-operations/snapshots/{snapshot_id}/analyze", response_model=OperationsSnapshot)
def analyze_snapshot(snapshot_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> OperationsSnapshot:
    try:
        return executive_operations_service.analyze(snapshot_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-operations/audit", response_model=list[AuditRecord])
def operations_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_operations_service.audit_records(workspace_id)
