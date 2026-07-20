from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    LifecycleStatusResponse,
    StrategyLifecycleAssessment,
    StrategyLifecycleAssessmentCreate,
)
from .service import executive_live_strategy_performance_lifecycle_service

router = APIRouter(tags=["executive-live-strategy-performance-lifecycle"])


@router.get("/v1/executive-live-strategy-performance-lifecycle/status", response_model=LifecycleStatusResponse)
def lifecycle_status(workspace_id: str = Query(min_length=1, max_length=100)) -> LifecycleStatusResponse:
    return executive_live_strategy_performance_lifecycle_service.status(workspace_id)


@router.post(
    "/v1/executive-live-strategy-performance-lifecycle/assessments",
    response_model=StrategyLifecycleAssessment,
    status_code=status.HTTP_201_CREATED,
)
def create_assessment(payload: StrategyLifecycleAssessmentCreate) -> StrategyLifecycleAssessment:
    try:
        return executive_live_strategy_performance_lifecycle_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/v1/executive-live-strategy-performance-lifecycle/assessments",
    response_model=list[StrategyLifecycleAssessment],
)
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[StrategyLifecycleAssessment]:
    return executive_live_strategy_performance_lifecycle_service.list_assessments(workspace_id)


@router.get(
    "/v1/executive-live-strategy-performance-lifecycle/assessments/{assessment_id}",
    response_model=StrategyLifecycleAssessment,
)
def get_assessment(
    assessment_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> StrategyLifecycleAssessment:
    item = executive_live_strategy_performance_lifecycle_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Strategy lifecycle assessment not found")
    return item


@router.get(
    "/v1/executive-live-strategy-performance-lifecycle/audit",
    response_model=list[AuditRecord],
)
def lifecycle_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_live_strategy_performance_lifecycle_service.audit(workspace_id)
