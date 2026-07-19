from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    RiskBrainRun,
    RiskBrainRunCreate,
    RiskBrainRunListResponse,
    RiskBrainStatusResponse,
)
from .service import executive_risk_brain_service

router = APIRouter(tags=["executive-risk-brain"])


@router.get("/v1/executive-risk-brain/status", response_model=RiskBrainStatusResponse)
def risk_brain_status(workspace_id: str = Query(min_length=1, max_length=100)) -> RiskBrainStatusResponse:
    return executive_risk_brain_service.status(workspace_id)


@router.post(
    "/v1/executive-risk-brain/runs",
    response_model=RiskBrainRun,
    status_code=status.HTTP_201_CREATED,
)
def create_risk_brain_run(payload: RiskBrainRunCreate) -> RiskBrainRun:
    try:
        return executive_risk_brain_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-risk-brain/runs", response_model=RiskBrainRunListResponse)
def list_risk_brain_runs(
    workspace_id: str = Query(min_length=1, max_length=100),
    account_profile_id: str | None = Query(default=None, min_length=1, max_length=100),
) -> RiskBrainRunListResponse:
    items = executive_risk_brain_service.list_runs(workspace_id, account_profile_id)
    return RiskBrainRunListResponse(items=items, count=len(items))


@router.get("/v1/executive-risk-brain/runs/{run_id}", response_model=RiskBrainRun)
def get_risk_brain_run(
    run_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> RiskBrainRun:
    item = executive_risk_brain_service.get(run_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive risk-brain run not found")
    return item


@router.get("/v1/executive-risk-brain/audit", response_model=list[AuditRecord])
def risk_brain_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_risk_brain_service.audit_records(workspace_id)
