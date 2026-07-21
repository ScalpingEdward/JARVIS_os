from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    PortfolioRiskAssessment,
    PortfolioRiskAssessmentCreate,
    PortfolioRiskAudit,
    PortfolioRiskExecuteRequest,
    PortfolioRiskStatus,
)
from .service import portfolio_risk_brain_service

router = APIRouter(tags=["executive-portfolio-risk-brain"])


@router.get("/v1/executive-portfolio-risk-brain/status", response_model=PortfolioRiskStatus)
def risk_status(workspace_id: str = Query(min_length=1, max_length=100)) -> PortfolioRiskStatus:
    return portfolio_risk_brain_service.status(workspace_id)


@router.post(
    "/v1/executive-portfolio-risk-brain/assessments",
    response_model=PortfolioRiskAssessment,
    status_code=status.HTTP_201_CREATED,
)
def create_assessment(payload: PortfolioRiskAssessmentCreate) -> PortfolioRiskAssessment:
    try:
        return portfolio_risk_brain_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-portfolio-risk-brain/assessments", response_model=list[PortfolioRiskAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[PortfolioRiskAssessment]:
    return portfolio_risk_brain_service.list_records(workspace_id)


@router.get("/v1/executive-portfolio-risk-brain/assessments/{record_id}", response_model=PortfolioRiskAssessment)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> PortfolioRiskAssessment:
    record = portfolio_risk_brain_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="risk assessment not found")
    return record


@router.post("/v1/executive-portfolio-risk-brain/assessments/{record_id}/execute", response_model=PortfolioRiskAssessment)
def execute_assessment(
    record_id: UUID,
    request: PortfolioRiskExecuteRequest,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> PortfolioRiskAssessment:
    try:
        return portfolio_risk_brain_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-portfolio-risk-brain/audit", response_model=list[PortfolioRiskAudit])
def risk_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[PortfolioRiskAudit]:
    return portfolio_risk_brain_service.audit_records(workspace_id)
