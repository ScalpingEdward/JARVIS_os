from fastapi import APIRouter, Header, HTTPException, Query

from .models import AuditEvent, SupervisionAction, SupervisionCreate, SupervisionRecord
from .service import ExecutionSupervisorError, ExecutionSupervisorService

router = APIRouter(prefix="/v1/execution-supervision", tags=["PHOENIX v21.11"])
service = ExecutionSupervisorService()


def _workspace(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=400, detail="X-Workspace-ID header is required")
    return value


@router.get("/status")
def status() -> dict[str, object]:
    return service.status()


@router.post("/records", response_model=SupervisionRecord, status_code=201)
def create_record(
    payload: SupervisionCreate,
    x_actor: str = Header(default="system", alias="X-Actor"),
) -> SupervisionRecord:
    try:
        return service.create(payload, actor=x_actor)
    except ExecutionSupervisorError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[SupervisionRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[SupervisionRecord]:
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=SupervisionRecord)
def get_record(record_id: str, x_workspace_id: str | None = Header(default=None, alias="X-Workspace-ID")) -> SupervisionRecord:
    try:
        return service.get(_workspace(x_workspace_id), record_id)
    except ExecutionSupervisorError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/execute", response_model=SupervisionRecord)
def execute_record(
    record_id: str,
    action: SupervisionAction,
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
) -> SupervisionRecord:
    try:
        return service.execute(_workspace(x_workspace_id), record_id, action)
    except ExecutionSupervisorError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(workspace_id: str = Query(min_length=1)) -> list[AuditEvent]:
    return service.audit(workspace_id)
