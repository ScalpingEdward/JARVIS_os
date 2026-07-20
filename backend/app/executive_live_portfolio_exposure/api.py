from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, LivePortfolioExposureAssessment, LivePortfolioExposureCreate, PortfolioStatusResponse
from .service import executive_live_portfolio_exposure_service

router = APIRouter(prefix="/v1/executive-live-portfolio-exposure", tags=["executive-live-portfolio-exposure"])


@router.get("/status", response_model=PortfolioStatusResponse)
def status_endpoint(workspace_id: str = Query(min_length=1, max_length=100)) -> PortfolioStatusResponse:
    return executive_live_portfolio_exposure_service.status(workspace_id)


@router.post("/assessments", response_model=LivePortfolioExposureAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: LivePortfolioExposureCreate) -> LivePortfolioExposureAssessment:
    try:
        return executive_live_portfolio_exposure_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/assessments", response_model=list[LivePortfolioExposureAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[LivePortfolioExposureAssessment]:
    return executive_live_portfolio_exposure_service.list_assessments(workspace_id)


@router.get("/assessments/{assessment_id}", response_model=LivePortfolioExposureAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> LivePortfolioExposureAssessment:
    record = executive_live_portfolio_exposure_service.get(assessment_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Live portfolio exposure assessment not found")
    return record


@router.get("/audit", response_model=list[AuditRecord])
def audit_endpoint(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_live_portfolio_exposure_service.audit(workspace_id)
