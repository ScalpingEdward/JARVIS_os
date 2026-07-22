from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, OrchestrationActionRequest, OrchestrationCreate, RecoveryOrchestration
from .service import RecoveryOrchestrationError, service

router = APIRouter(prefix="/v1/recovery-orchestration", tags=["PHOENIX v21.35 Recovery Orchestration"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "recovery-orchestration", "version": "21.35", "status": "ready"}


@router.post("/orchestrations", response_model=RecoveryOrchestration)
def create_orchestration(payload: OrchestrationCreate) -> RecoveryOrchestration:
    try:
        return service.create(payload)
    except RecoveryOrchestrationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/orchestrations", response_model=list[RecoveryOrchestration])
def list_orchestrations(x_workspace_id: str = Header(...)) -> list[RecoveryOrchestration]:
    return service.list(x_workspace_id)


@router.get("/orchestrations/{record_id}", response_model=RecoveryOrchestration)
def get_orchestration(record_id: str, x_workspace_id: str = Header(...)) -> RecoveryOrchestration:
    try:
        return service.get(record_id, x_workspace_id)
    except RecoveryOrchestrationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/orchestrations/{record_id}/actions", response_model=RecoveryOrchestration)
def act_on_orchestration(record_id: str, request: OrchestrationActionRequest, x_workspace_id: str = Header(...)) -> RecoveryOrchestration:
    try:
        return service.act(record_id, x_workspace_id, request)
    except RecoveryOrchestrationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
