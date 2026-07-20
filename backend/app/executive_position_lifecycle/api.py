from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, PositionActionRequest, PositionLifecycleAssessment, PositionLifecycleAssessmentCreate, PositionLifecycleStatusResponse
from .service import executive_position_lifecycle_service

router = APIRouter(tags=["executive-position-lifecycle"])


@router.get("/v1/executive-position-lifecycle/status", response_model=PositionLifecycleStatusResponse)
def position_lifecycle_status(workspace_id: str = Query(min_length=1, max_length=100)) -> PositionLifecycleStatusResponse:
    return executive_position_lifecycle_service.status(workspace_id)


@router.post("/v1/executive-position-lifecycle/positions", response_model=PositionLifecycleAssessment, status_code=status.HTTP_201_CREATED)
def create_position_lifecycle(payload: PositionLifecycleAssessmentCreate) -> PositionLifecycleAssessment:
    try:
        return executive_position_lifecycle_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-position-lifecycle/positions", response_model=list[PositionLifecycleAssessment])
def list_position_lifecycles(workspace_id: str = Query(min_length=1, max_length=100)) -> list[PositionLifecycleAssessment]:
    return executive_position_lifecycle_service.list_positions(workspace_id)


@router.get("/v1/executive-position-lifecycle/positions/{record_id}", response_model=PositionLifecycleAssessment)
def get_position_lifecycle(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> PositionLifecycleAssessment:
    record = executive_position_lifecycle_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Position lifecycle record not found")
    return record


@router.post("/v1/executive-position-lifecycle/close", response_model=PositionLifecycleAssessment)
def close_position(request: PositionActionRequest) -> PositionLifecycleAssessment:
    try:
        return executive_position_lifecycle_service.close(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-position-lifecycle/audit", response_model=list[AuditRecord])
def position_lifecycle_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_position_lifecycle_service.audit_records(workspace_id)
