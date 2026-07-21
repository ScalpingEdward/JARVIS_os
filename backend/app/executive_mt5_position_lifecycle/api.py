from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, MT5PositionLifecycleCreate, MT5PositionLifecycleRecord, PositionActionRequest, PositionLifecycleStatusResponse
from .service import executive_mt5_position_lifecycle_service

router = APIRouter(tags=["executive-mt5-position-lifecycle"])


@router.get("/v1/executive-mt5-position-lifecycle/status", response_model=PositionLifecycleStatusResponse)
def lifecycle_status(workspace_id: str = Query(min_length=1, max_length=100)) -> PositionLifecycleStatusResponse:
    return executive_mt5_position_lifecycle_service.status(workspace_id)


@router.post("/v1/executive-mt5-position-lifecycle/assessments", response_model=MT5PositionLifecycleRecord, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: MT5PositionLifecycleCreate) -> MT5PositionLifecycleRecord:
    try:
        return executive_mt5_position_lifecycle_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-position-lifecycle/assessments", response_model=list[MT5PositionLifecycleRecord])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[MT5PositionLifecycleRecord]:
    return executive_mt5_position_lifecycle_service.list_records(workspace_id)


@router.get("/v1/executive-mt5-position-lifecycle/assessments/{record_id}", response_model=MT5PositionLifecycleRecord)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> MT5PositionLifecycleRecord:
    record = executive_mt5_position_lifecycle_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Position lifecycle assessment not found")
    return record


@router.post("/v1/executive-mt5-position-lifecycle/execute", response_model=MT5PositionLifecycleRecord)
def execute_action(request: PositionActionRequest) -> MT5PositionLifecycleRecord:
    try:
        return executive_mt5_position_lifecycle_service.execute(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-position-lifecycle/audit", response_model=list[AuditRecord])
def lifecycle_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_mt5_position_lifecycle_service.audit(workspace_id)
