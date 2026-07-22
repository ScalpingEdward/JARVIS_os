from fastapi import APIRouter, Header, HTTPException, Query

from .models import AuditEvent, ExecutionPlanAction, ExecutionPlanCreate, ExecutionPlanRecord
from .service import ExecutionPlanError, ExecutiveExecutionPlannerService

router = APIRouter(prefix="/v1/execution-planning", tags=["executive-execution-planner"])
service = ExecutiveExecutionPlannerService()


def _workspace(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=400, detail="X-Workspace-ID header is required")
    return value


@router.get("/status")
def status() -> dict[str, object]:
    return service.status()


@router.post("/records", response_model=ExecutionPlanRecord, status_code=201)
def create_record(
    payload: ExecutionPlanCreate,
    x_actor: str = Header(default="api", alias="X-Actor"),
) -> ExecutionPlanRecord:
    try:
        return service.create(payload, actor=x_actor)
    except ExecutionPlanError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ExecutionPlanRecord])
def list_records(x_workspace_id: str | None = Header(default=None, alias="X-Workspace-ID")) -> list[ExecutionPlanRecord]:
    return service.list(_workspace(x_workspace_id))


@router.get("/records/{record_id}", response_model=ExecutionPlanRecord)
def get_record(
    record_id: str,
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
) -> ExecutionPlanRecord:
    try:
        return service.get(_workspace(x_workspace_id), record_id)
    except ExecutionPlanError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/execute", response_model=ExecutionPlanRecord)
def execute_record(
    record_id: str,
    action: ExecutionPlanAction,
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
) -> ExecutionPlanRecord:
    try:
        return service.execute(_workspace(x_workspace_id), record_id, action)
    except ExecutionPlanError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[AuditEvent]:
    return service.audit(_workspace(x_workspace_id))[-limit:]
