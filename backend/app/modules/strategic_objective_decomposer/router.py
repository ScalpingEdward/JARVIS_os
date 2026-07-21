from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from .models import StrategicObjectiveCreate, StrategicObjectiveExecuteRequest
from .service import strategic_objective_decomposer_service

router = APIRouter(prefix="/v1/strategic-objectives", tags=["strategic-objectives"])


def _workspace(x_workspace_id: str | None) -> str:
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-ID header required")
    return x_workspace_id


@router.get("/status")
def status(x_workspace_id: str | None = Header(default=None)):
    return strategic_objective_decomposer_service.status(_workspace(x_workspace_id))


@router.post("/records")
def create_record(payload: StrategicObjectiveCreate, x_workspace_id: str | None = Header(default=None)):
    workspace_id = _workspace(x_workspace_id)
    if payload.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="workspace mismatch")
    try:
        return strategic_objective_decomposer_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records")
def list_records(x_workspace_id: str | None = Header(default=None)):
    return strategic_objective_decomposer_service.list_records(_workspace(x_workspace_id))


@router.get("/records/{record_id}")
def get_record(record_id: UUID, x_workspace_id: str | None = Header(default=None)):
    record = strategic_objective_decomposer_service.get(record_id, _workspace(x_workspace_id))
    if record is None:
        raise HTTPException(status_code=404, detail="strategic objective record not found")
    return record


@router.post("/records/{record_id}/execute")
def execute_record(
    record_id: UUID,
    request: StrategicObjectiveExecuteRequest,
    x_workspace_id: str | None = Header(default=None),
):
    try:
        return strategic_objective_decomposer_service.execute(record_id, _workspace(x_workspace_id), request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(x_workspace_id: str | None = Header(default=None)):
    return strategic_objective_decomposer_service.audit_records(_workspace(x_workspace_id))
