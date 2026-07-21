from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query

from .models import (
    ImprovementPlanningAudit,
    ImprovementPlanningCreate,
    ImprovementPlanningExecuteRequest,
    ImprovementPlanningRecord,
    ImprovementPlanningStatus,
)
from .service import improvement_planning_service

router = APIRouter(prefix="/v1/executive-improvement-planning", tags=["executive-improvement-planning"])


@router.get("/status", response_model=ImprovementPlanningStatus)
def status(workspace_id: str = Query(min_length=1)) -> ImprovementPlanningStatus:
    return improvement_planning_service.status(workspace_id)


@router.post("/tasks", response_model=ImprovementPlanningRecord)
def create_task(payload: ImprovementPlanningCreate) -> ImprovementPlanningRecord:
    try:
        return improvement_planning_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/tasks", response_model=list[ImprovementPlanningRecord])
def list_tasks(workspace_id: str = Query(min_length=1)) -> list[ImprovementPlanningRecord]:
    return improvement_planning_service.list_records(workspace_id)


@router.get("/tasks/{record_id}", response_model=ImprovementPlanningRecord)
def get_task(record_id: UUID, workspace_id: str = Query(min_length=1)) -> ImprovementPlanningRecord:
    record = improvement_planning_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="improvement planning record not found")
    return record


@router.post("/tasks/{record_id}/execute", response_model=ImprovementPlanningRecord)
def execute_task(
    record_id: UUID,
    request: ImprovementPlanningExecuteRequest,
    workspace_id: str = Header(alias="X-Workspace-ID", min_length=1),
) -> ImprovementPlanningRecord:
    try:
        return improvement_planning_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[ImprovementPlanningAudit])
def audit(workspace_id: str = Query(min_length=1)) -> list[ImprovementPlanningAudit]:
    return improvement_planning_service.audit_records(workspace_id)
