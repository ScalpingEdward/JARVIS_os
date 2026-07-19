from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AdaptiveScoringStatusResponse,
    AuditRecord,
    ScoringRun,
    ScoringRunCreate,
    ScoringRunListResponse,
)
from .service import executive_adaptive_strategy_scoring_service

router = APIRouter(tags=["executive-adaptive-strategy-scoring"])


@router.get(
    "/v1/executive-adaptive-strategy-scoring/status",
    response_model=AdaptiveScoringStatusResponse,
)
def adaptive_scoring_status(
    workspace_id: str = Query(min_length=1, max_length=100),
) -> AdaptiveScoringStatusResponse:
    return executive_adaptive_strategy_scoring_service.status(workspace_id)


@router.post(
    "/v1/executive-adaptive-strategy-scoring/runs",
    response_model=ScoringRun,
    status_code=status.HTTP_201_CREATED,
)
def create_scoring_run(payload: ScoringRunCreate) -> ScoringRun:
    return executive_adaptive_strategy_scoring_service.create_run(payload)


@router.get(
    "/v1/executive-adaptive-strategy-scoring/runs",
    response_model=ScoringRunListResponse,
)
def list_scoring_runs(
    workspace_id: str = Query(min_length=1, max_length=100),
    account_profile_id: str | None = Query(default=None, min_length=1, max_length=100),
) -> ScoringRunListResponse:
    items = executive_adaptive_strategy_scoring_service.list_runs(workspace_id, account_profile_id)
    return ScoringRunListResponse(items=items, count=len(items))


@router.get(
    "/v1/executive-adaptive-strategy-scoring/runs/{run_id}",
    response_model=ScoringRun,
)
def get_scoring_run(
    run_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> ScoringRun:
    item = executive_adaptive_strategy_scoring_service.get(run_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Adaptive strategy scoring run not found")
    return item


@router.get(
    "/v1/executive-adaptive-strategy-scoring/audit",
    response_model=list[AuditRecord],
)
def adaptive_scoring_audit(
    workspace_id: str = Query(min_length=1, max_length=100),
) -> list[AuditRecord]:
    return executive_adaptive_strategy_scoring_service.audit_records(workspace_id)
