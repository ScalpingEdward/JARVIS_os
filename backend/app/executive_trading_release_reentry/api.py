from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ReleaseAssessment, ReleaseAssessmentCreate, ReleaseListResponse, ReleaseStatusResponse
from .service import executive_trading_release_reentry_service

router = APIRouter(tags=["executive-trading-release-reentry"])


@router.get("/v1/executive-trading-release-reentry/status", response_model=ReleaseStatusResponse)
def release_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ReleaseStatusResponse:
    return executive_trading_release_reentry_service.status(workspace_id)


@router.post("/v1/executive-trading-release-reentry/assessments", response_model=ReleaseAssessment, status_code=status.HTTP_201_CREATED)
def create_release_assessment(payload: ReleaseAssessmentCreate) -> ReleaseAssessment:
    try:
        return executive_trading_release_reentry_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-trading-release-reentry/assessments", response_model=ReleaseListResponse)
def list_release_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> ReleaseListResponse:
    items = executive_trading_release_reentry_service.list_assessments(workspace_id)
    return ReleaseListResponse(items=items, count=len(items))


@router.get("/v1/executive-trading-release-reentry/assessments/{assessment_id}", response_model=ReleaseAssessment)
def get_release_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ReleaseAssessment:
    item = executive_trading_release_reentry_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Trading release assessment not found")
    return item


@router.get("/v1/executive-trading-release-reentry/audit", response_model=list[AuditRecord])
def release_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_trading_release_reentry_service.audit_records(workspace_id)
