from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    DeploymentStatusResponse,
    LiveCapitalDeploymentAssessment,
    LiveCapitalDeploymentCreate,
)
from .service import executive_live_capital_broker_deployment_service

router = APIRouter(prefix="/v1/executive-live-capital-broker-deployment", tags=["executive-live-capital-broker-deployment"])


@router.get("/status", response_model=DeploymentStatusResponse)
def deployment_status(workspace_id: str = Query(min_length=1, max_length=100)) -> DeploymentStatusResponse:
    return executive_live_capital_broker_deployment_service.status(workspace_id)


@router.post("/assessments", response_model=LiveCapitalDeploymentAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: LiveCapitalDeploymentCreate) -> LiveCapitalDeploymentAssessment:
    try:
        return executive_live_capital_broker_deployment_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/assessments", response_model=list[LiveCapitalDeploymentAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[LiveCapitalDeploymentAssessment]:
    return executive_live_capital_broker_deployment_service.list_assessments(workspace_id)


@router.get("/assessments/{assessment_id}", response_model=LiveCapitalDeploymentAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> LiveCapitalDeploymentAssessment:
    record = executive_live_capital_broker_deployment_service.get(assessment_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Live capital deployment assessment not found")
    return record


@router.get("/audit", response_model=list[AuditRecord])
def deployment_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_live_capital_broker_deployment_service.audit(workspace_id)
