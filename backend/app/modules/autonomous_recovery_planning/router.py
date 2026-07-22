from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, RecoveryActionRequest, RecoveryPlan, RecoveryPlanCreate
from .service import AutonomousRecoveryPlanningError, service

router = APIRouter(prefix="/v1/recovery-planning", tags=["PHOENIX v21.34 Recovery Planning"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "autonomous-recovery-planning", "version": "21.34", "status": "ready"}


@router.post("/plans", response_model=RecoveryPlan)
def create_plan(payload: RecoveryPlanCreate) -> RecoveryPlan:
    try:
        return service.create(payload)
    except AutonomousRecoveryPlanningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/plans", response_model=list[RecoveryPlan])
def list_plans(x_workspace_id: str = Header(...)) -> list[RecoveryPlan]:
    return service.list(x_workspace_id)


@router.get("/plans/{record_id}", response_model=RecoveryPlan)
def get_plan(record_id: str, x_workspace_id: str = Header(...)) -> RecoveryPlan:
    try:
        return service.get(record_id, x_workspace_id)
    except AutonomousRecoveryPlanningError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/plans/{record_id}/actions", response_model=RecoveryPlan)
def act_on_plan(
    record_id: str,
    request: RecoveryActionRequest,
    x_workspace_id: str = Header(...),
) -> RecoveryPlan:
    try:
        return service.act(record_id, x_workspace_id, request)
    except AutonomousRecoveryPlanningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
