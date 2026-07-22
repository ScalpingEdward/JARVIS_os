from fastapi import APIRouter, Header, HTTPException

from .models import DeploymentVerificationCreate, DeploymentVerificationRecord, VerificationAction
from .service import DeploymentVerificationError, service

router = APIRouter(prefix="/v1/deployment-lineage-verification", tags=["PHOENIX v21.30"])


def workspace(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=400, detail="X-Workspace-ID header is required")
    return value


@router.get("/status")
def status() -> dict[str, object]:
    return service.status()


@router.post("/verifications", response_model=DeploymentVerificationRecord)
def create_verification(payload: DeploymentVerificationCreate) -> DeploymentVerificationRecord:
    try:
        return service.create(payload)
    except DeploymentVerificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/verifications", response_model=list[DeploymentVerificationRecord])
def list_verifications(x_workspace_id: str | None = Header(default=None)) -> list[DeploymentVerificationRecord]:
    return service.list(workspace(x_workspace_id))


@router.get("/verifications/{record_id}", response_model=DeploymentVerificationRecord)
def get_verification(record_id: str, x_workspace_id: str | None = Header(default=None)) -> DeploymentVerificationRecord:
    try:
        return service.get(workspace(x_workspace_id), record_id)
    except DeploymentVerificationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/verifications/{record_id}/actions", response_model=DeploymentVerificationRecord)
def act_on_verification(
    record_id: str,
    payload: VerificationAction,
    x_workspace_id: str | None = Header(default=None),
) -> DeploymentVerificationRecord:
    try:
        return service.act(workspace(x_workspace_id), record_id, payload)
    except DeploymentVerificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(x_workspace_id: str | None = Header(default=None)) -> list[dict[str, object]]:
    return [item.model_dump() for item in service.audit(workspace(x_workspace_id))]
