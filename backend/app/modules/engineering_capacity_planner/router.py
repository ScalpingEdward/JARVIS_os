from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from .models import CapacityPlanningCreate, CapacityPlanningExecuteRequest
from .service import engineering_capacity_planner_service

router = APIRouter(prefix="/v1/engineering-capacity-planning", tags=["engineering-capacity-planning"])


def _workspace(x_workspace_id: str | None) -> str:
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-ID header required")
    return x_workspace_id


@router.get("/status")
def status(x_workspace_id: str | None = Header(default=None)):
    return engineering_capacity_planner_service.status(_workspace(x_workspace_id))


@router.post("/records", status_code=201)
def create_record(payload: CapacityPlanningCreate, x_workspace_id: str | None = Header(default=None)):
    workspace_id = _workspace(x_workspace_id)
    if payload.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="workspace mismatch")
    try:
        return engineering_capacity_planner_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records")
def list_records(x_workspace_id: str | None = Header(default=None)):
    return engineering_capacity_planner_service.list_records(_workspace(x_workspace_id))


@router.get("/records/{record_id}")
def get_record(record_id: UUID, x_workspace_id: str | None = Header(default=None)):
    record = engineering_capacity_planner_service.get(record_id, _workspace(x_workspace_id))
    if record is None:
        raise HTTPException(status_code=404, detail="capacity planning record not found")
    return record


@router.post("/records/{record_id}/execute")
def execute_record(record_id: UUID, payload: CapacityPlanningExecuteRequest, x_workspace_id: str | None = Header(default=None)):
    try:
        return engineering_capacity_planner_service.execute(record_id, _workspace(x_workspace_id), payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(x_workspace_id: str | None = Header(default=None)):
    return engineering_capacity_planner_service.audit_records(_workspace(x_workspace_id))
