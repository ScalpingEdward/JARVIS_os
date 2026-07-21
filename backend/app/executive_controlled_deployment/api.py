from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from .models import ControlledDeploymentCreate, ControlledDeploymentRecord, ControlledDeploymentStatus, DeploymentExecuteRequest
from .service import controlled_deployment_service

router = APIRouter(prefix="/v1/executive-controlled-deployment", tags=["executive-controlled-deployment"])


@router.get("/status", response_model=ControlledDeploymentStatus)
def status(x_workspace_id: str = Header(...)):
    return controlled_deployment_service.status(x_workspace_id)


@router.post("/deployments", response_model=ControlledDeploymentRecord)
def create_deployment(payload: ControlledDeploymentCreate):
    try:
        return controlled_deployment_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/deployments", response_model=list[ControlledDeploymentRecord])
def list_deployments(x_workspace_id: str = Header(...)):
    return controlled_deployment_service.list_records(x_workspace_id)


@router.get("/deployments/{record_id}", response_model=ControlledDeploymentRecord)
def get_deployment(record_id: UUID, x_workspace_id: str = Header(...)):
    record = controlled_deployment_service.get(record_id, x_workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="deployment record not found")
    return record


@router.post("/deployments/{record_id}/execute", response_model=ControlledDeploymentRecord)
def execute_deployment(record_id: UUID, request: DeploymentExecuteRequest, x_workspace_id: str = Header(...)):
    try:
        return controlled_deployment_service.execute(record_id, x_workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(x_workspace_id: str = Header(...)):
    return controlled_deployment_service.audit_records(x_workspace_id)
