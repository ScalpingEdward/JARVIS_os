from fastapi import APIRouter, Header, HTTPException, status

from .models import AuditEvent, RuntimeAction, RuntimeCreate, RuntimeRecord
from .service import RuntimeSupervisorError, service

router = APIRouter(prefix="/v1/runtime-supervisor", tags=["PHOENIX v21.24 Runtime Supervisor"])


def workspace(x_workspace_id: str = Header(..., alias="X-Workspace-ID")) -> str:
    return x_workspace_id


@router.get("/status")
def get_status() -> dict[str, str]:
    return {"module": "runtime-supervisor", "version": "21.24", "status": "ready"}


@router.post("/runtimes", response_model=RuntimeRecord, status_code=status.HTTP_201_CREATED)
def create_runtime(payload: RuntimeCreate) -> RuntimeRecord:
    try:
        return service.create(payload)
    except RuntimeSupervisorError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/runtimes", response_model=list[RuntimeRecord])
def list_runtimes(x_workspace_id: str = Header(..., alias="X-Workspace-ID")) -> list[RuntimeRecord]:
    return service.list(x_workspace_id)


@router.get("/runtimes/{record_id}", response_model=RuntimeRecord)
def get_runtime(record_id: str, x_workspace_id: str = Header(..., alias="X-Workspace-ID")) -> RuntimeRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except RuntimeSupervisorError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/runtimes/{record_id}/actions", response_model=RuntimeRecord)
def runtime_action(
    record_id: str,
    payload: RuntimeAction,
    x_workspace_id: str = Header(..., alias="X-Workspace-ID"),
) -> RuntimeRecord:
    try:
        return service.act(record_id, x_workspace_id, payload)
    except RuntimeSupervisorError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def get_audit(x_workspace_id: str = Header(..., alias="X-Workspace-ID")) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
