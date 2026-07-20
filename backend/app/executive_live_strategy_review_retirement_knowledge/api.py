from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ReviewStatusResponse, StrategyReviewAssessment, StrategyReviewCreate
from .service import executive_live_strategy_review_retirement_knowledge_service

router = APIRouter(tags=["executive-live-strategy-review-retirement-knowledge"])


@router.get("/v1/executive-live-strategy-review-retirement-knowledge/status", response_model=ReviewStatusResponse)
def review_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ReviewStatusResponse:
    return executive_live_strategy_review_retirement_knowledge_service.status(workspace_id)


@router.post(
    "/v1/executive-live-strategy-review-retirement-knowledge/assessments",
    response_model=StrategyReviewAssessment,
    status_code=status.HTTP_201_CREATED,
)
def create_assessment(payload: StrategyReviewCreate) -> StrategyReviewAssessment:
    try:
        return executive_live_strategy_review_retirement_knowledge_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/v1/executive-live-strategy-review-retirement-knowledge/assessments",
    response_model=list[StrategyReviewAssessment],
)
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[StrategyReviewAssessment]:
    return executive_live_strategy_review_retirement_knowledge_service.list_assessments(workspace_id)


@router.get(
    "/v1/executive-live-strategy-review-retirement-knowledge/assessments/{assessment_id}",
    response_model=StrategyReviewAssessment,
)
def get_assessment(
    assessment_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> StrategyReviewAssessment:
    item = executive_live_strategy_review_retirement_knowledge_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Strategy review assessment not found")
    return item


@router.get(
    "/v1/executive-live-strategy-review-retirement-knowledge/audit",
    response_model=list[AuditRecord],
)
def review_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_live_strategy_review_retirement_knowledge_service.audit(workspace_id)
