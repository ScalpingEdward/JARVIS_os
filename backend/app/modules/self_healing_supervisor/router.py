from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, SelfHealingSupervisor, SupervisorActionRequest, SupervisorCreate
from .service import SelfHealingSupervisorError, service

router = APIRouter(prefix="/v1/self-healing-supervisor", tags=["PHOENIX v21.36 Self-Healing Supervisor"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "self-healing-supervisor", "version": "21.36", "status": "ready"}


@router.post("/supervisors", response_model=SelfHealingSupervisor)
def create_supervisor(payload: SupervisorCreate) -> SelfHealingSupervisor:
    try:
        return service.create(payload)
    except SelfHealingSupervisorError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/supervisors", response_model=list[SelfHealingSupervisor])
def list_supervisors(x_workspace_id: str = Header(...)) -> list[SelfHealingSupervisor]:
    return service.list(x_workspace_id)


@router.get("/supervisors/{record_id}", response_model=SelfHealingSupervisor)
def get_supervisor(record_id: str, x_workspace_id: str = Header(...)) -> SelfHealingSupervisor:
    try:
        return service.get(record_id, x_workspace_id)
    except SelfHealingSupervisorError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/supervisors/{record_id}/actions", response_model=SelfHealingSupervisor)
def act_on_supervisor(record_id: str, request: SupervisorActionRequest, x_workspace_id: str = Header(...)) -> SelfHealingSupervisor:
    try:
        return service.act(record_id, x_workspace_id, request)
    except SelfHealingSupervisorError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
