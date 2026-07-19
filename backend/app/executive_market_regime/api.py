from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    MarketRegimeAssessment,
    RegimeAssessmentCreate,
    RegimeAssessmentListResponse,
    RegimeStatusResponse,
    RegimeStrategyEvaluationRequest,
    RegimeStrategyEvaluationResponse,
)
from .service import executive_market_regime_service

router = APIRouter(tags=["executive-market-regime"])


@router.get("/v1/executive-market-regime/status", response_model=RegimeStatusResponse)
def market_regime_status(workspace_id: str = Query(min_length=1, max_length=100)) -> RegimeStatusResponse:
    return executive_market_regime_service.status(workspace_id)


@router.post(
    "/v1/executive-market-regime/assessments",
    response_model=MarketRegimeAssessment,
    status_code=status.HTTP_201_CREATED,
)
def create_market_regime_assessment(payload: RegimeAssessmentCreate) -> MarketRegimeAssessment:
    return executive_market_regime_service.assess(payload)


@router.get("/v1/executive-market-regime/assessments", response_model=RegimeAssessmentListResponse)
def list_market_regime_assessments(
    workspace_id: str = Query(min_length=1, max_length=100),
    account_profile_id: str | None = Query(default=None, min_length=1, max_length=100),
) -> RegimeAssessmentListResponse:
    items = executive_market_regime_service.list_assessments(workspace_id, account_profile_id)
    return RegimeAssessmentListResponse(items=items, count=len(items))


@router.get("/v1/executive-market-regime/assessments/{assessment_id}", response_model=MarketRegimeAssessment)
def get_market_regime_assessment(
    assessment_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> MarketRegimeAssessment:
    item = executive_market_regime_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Market-regime assessment not found")
    return item


@router.post(
    "/v1/executive-market-regime/assessments/{assessment_id}/evaluate-strategies",
    response_model=RegimeStrategyEvaluationResponse,
)
def evaluate_strategies(
    assessment_id: UUID,
    payload: RegimeStrategyEvaluationRequest,
) -> RegimeStrategyEvaluationResponse:
    try:
        return executive_market_regime_service.evaluate_strategies(assessment_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-market-regime/audit", response_model=list[AuditRecord])
def market_regime_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_market_regime_service.audit_records(workspace_id)
