from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, RolloutAction, RolloutCreate, RolloutRecord
from .service import CanaryRolloutError, service

router = APIRouter(prefix="/v1/canary-rollout-governance", tags=["canary-rollout-governance"])


def _workspace(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=400, detail="X-Workspace-ID header required")
    return value


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "canary-rollout-governance", "version": "v21.29", "status": "ready"}


@router.post("/rollouts", response_model=RolloutRecord)
def create_rollout(payload: RolloutCreate, x_workspace_id: str | None = Header(default=None)) -> RolloutRecord:
    workspace_id = _workspace(x_workspace_id)
    if payload.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="workspace mismatch")
    try:
        return service.create(payload)
    except CanaryRolloutError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/rollouts", response_model=list[RolloutRecord])
def list_rollouts(x_workspace_id: str | None = Header(default=None)) -> list[RolloutRecord]:
    return service.list(_workspace(x_workspace_id))


@router.get("/rollouts/{record_id}", response_model=RolloutRecord)
def get_rollout(record_id: str, x_workspace_id: str | None = Header(default=None)) -> RolloutRecord:
    try:
        return service.get(record_id, _workspace(x_workspace_id))
    except CanaryRolloutError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/rollouts/{record_id}/actions", response_model=RolloutRecord)
def act_on_rollout(
    record_id: str,
    action: RolloutAction,
    x_workspace_id: str | None = Header(default=None),
) -> RolloutRecord:
    try:
        return service.act(record_id, _workspace(x_workspace_id), action)
    except CanaryRolloutError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str | None = Header(default=None)) -> list[AuditEvent]:
    return service.audit(_workspace(x_workspace_id))
