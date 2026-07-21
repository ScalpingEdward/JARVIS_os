from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    PortfolioExposureAssessment,
    PortfolioExposureAssessmentCreate,
    PortfolioExposureExecuteRequest,
    PortfolioExposureStatus,
)
from .service import portfolio_correlation_exposure_service

router = APIRouter(tags=["executive-mt5-portfolio-correlation-exposure"])


@router.get("/v1/executive-mt5-portfolio-exposure/status", response_model=PortfolioExposureStatus)
def portfolio_exposure_status(workspace_id: str = Query(min_length=1, max_length=100)) -> PortfolioExposureStatus:
    return portfolio_correlation_exposure_service.status(workspace_id)


@router.post("/v1/executive-mt5-portfolio-exposure/assessments", response_model=PortfolioExposureAssessment, status_code=status.HTTP_201_CREATED)
def create_portfolio_exposure_assessment(payload: PortfolioExposureAssessmentCreate) -> PortfolioExposureAssessment:
    try:
        return portfolio_correlation_exposure_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-portfolio-exposure/assessments", response_model=list[PortfolioExposureAssessment])
def list_portfolio_exposure_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[PortfolioExposureAssessment]:
    return portfolio_correlation_exposure_service.list_records(workspace_id)


@router.get("/v1/executive-mt5-portfolio-exposure/assessments/{record_id}", response_model=PortfolioExposureAssessment)
def get_portfolio_exposure_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> PortfolioExposureAssessment:
    record = portfolio_correlation_exposure_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Portfolio exposure assessment not found")
    return record


@router.post("/v1/executive-mt5-portfolio-exposure/assessments/{record_id}/execute", response_model=PortfolioExposureAssessment)
def execute_portfolio_exposure_assessment(record_id: UUID, request: PortfolioExposureExecuteRequest, workspace_id: str = Query(min_length=1, max_length=100)) -> PortfolioExposureAssessment:
    try:
        return portfolio_correlation_exposure_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-portfolio-exposure/audit", response_model=list[AuditRecord])
def portfolio_exposure_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return portfolio_correlation_exposure_service.audit_records(workspace_id)
