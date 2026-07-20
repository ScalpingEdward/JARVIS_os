from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    RebalancingAssessment,
    RebalancingAssessmentCreate,
    RebalancingStatusResponse,
)
from .service import executive_live_rebalancing_strategy_rotation_service

router = APIRouter(tags=["executive-live-rebalancing-strategy-rotation"])


@router.get(
    "/v1/executive-live-rebalancing-strategy-rotation/status",
    response_model=RebalancingStatusResponse,
)
def rebalancing_status(
    workspace_id: str = Query(min_length=1, max_length=100),
) -> RebalancingStatusResponse:
    return executive_live_rebalancing_strategy_rotation_service.status(workspace_id)


@router.post(
    "/v1/executive-live-rebalancing-strategy-rotation/assessments",
    response_model=RebalancingAssessment,
    status_code=status.HTTP_201_CREATED,
)
def create_rebalancing_assessment(
    payload: RebalancingAssessmentCreate,
) -> RebalancingAssessment:
    try:
        return executive_live_rebalancing_strategy_rotation_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/v1/executive-live-rebalancing-strategy-rotation/assessments",
    response_model=list[RebalancingAssessment],
)
def list_rebalancing_assessments(
    workspace_id: str = Query(min_length=1, max_length=100),
) -> list[RebalancingAssessment]:
    return executive_live_rebalancing_strategy_rotation_service.list_assessments(workspace_id)


@router.get(
    "/v1/executive-live-rebalancing-strategy-rotation/assessments/{assessment_id}",
    response_model=RebalancingAssessment,
)
def get_rebalancing_assessment(
    assessment_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> RebalancingAssessment:
    record = executive_live_rebalancing_strategy_rotation_service.get(
        assessment_id, workspace_id
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Rebalancing assessment not found")
    return record


@router.get(
    "/v1/executive-live-rebalancing-strategy-rotation/audit",
    response_model=list[AuditRecord],
)
def rebalancing_audit(
    workspace_id: str = Query(min_length=1, max_length=100),
) -> list[AuditRecord]:
    return executive_live_rebalancing_strategy_rotation_service.audit(workspace_id)
