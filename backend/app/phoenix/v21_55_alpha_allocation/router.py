from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, CapitalDeploymentRecord, DeploymentActionRequest, DeploymentCreate
from .service import CapitalDeploymentError, service

router = APIRouter(
    prefix="/v1/alpha-allocation",
    tags=["PHOENIX v21.55 Alpha Allocation Capital Deployment"],
)


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "alpha-allocation-capital-deployment", "version": "21.55", "status": "ready"}


@router.post("/records", response_model=CapitalDeploymentRecord)
def create_record(payload: DeploymentCreate) -> CapitalDeploymentRecord:
    try:
        return service.create(payload)
    except CapitalDeploymentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[CapitalDeploymentRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[CapitalDeploymentRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=CapitalDeploymentRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> CapitalDeploymentRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except CapitalDeploymentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=CapitalDeploymentRecord)
def act_on_record(record_id: str, request: DeploymentActionRequest, x_workspace_id: str = Header(...)) -> CapitalDeploymentRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except CapitalDeploymentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
