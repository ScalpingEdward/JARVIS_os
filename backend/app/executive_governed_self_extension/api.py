from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query

from .models import CodeChangeExecuteRequest, CodeChangePlan, CodeChangeRequest, SelfExtensionAudit, SelfExtensionStatus
from .service import governed_self_extension_service

router = APIRouter(prefix="/v1/executive-governed-self-extension", tags=["executive-governed-self-extension"])


@router.get("/status", response_model=SelfExtensionStatus)
def status(workspace_id: str = Query(...)):
    return governed_self_extension_service.status(workspace_id)


@router.post("/plans", response_model=CodeChangePlan)
def create_plan(payload: CodeChangeRequest):
    try:
        return governed_self_extension_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/plans", response_model=list[CodeChangePlan])
def list_plans(workspace_id: str = Query(...)):
    return governed_self_extension_service.list_plans(workspace_id)


@router.get("/plans/{plan_id}", response_model=CodeChangePlan)
def get_plan(plan_id: UUID, workspace_id: str = Query(...)):
    plan = governed_self_extension_service.get(plan_id, workspace_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="change plan not found")
    return plan


@router.post("/plans/{plan_id}/execute", response_model=CodeChangePlan)
def execute_plan(plan_id: UUID, request: CodeChangeExecuteRequest, workspace_id: str = Header(alias="X-Workspace-ID")):
    try:
        return governed_self_extension_service.execute(plan_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[SelfExtensionAudit])
def audit(workspace_id: str = Query(...)):
    return governed_self_extension_service.audit_records(workspace_id)
