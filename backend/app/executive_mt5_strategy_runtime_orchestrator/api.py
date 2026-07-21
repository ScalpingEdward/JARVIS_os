from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    StrategyRuntimeAssessment,
    StrategyRuntimeAssessmentCreate,
    StrategyRuntimeExecuteRequest,
    StrategyRuntimeStatus,
)
from .service import strategy_runtime_orchestrator_service

router = APIRouter(tags=["executive-mt5-strategy-runtime-orchestrator"])


@router.get("/v1/executive-mt5-strategy-runtime/status", response_model=StrategyRuntimeStatus)
def runtime_status(workspace_id: str = Query(min_length=1, max_length=100)) -> StrategyRuntimeStatus:
    return strategy_runtime_orchestrator_service.status(workspace_id)


@router.post("/v1/executive-mt5-strategy-runtime/assessments", response_model=StrategyRuntimeAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: StrategyRuntimeAssessmentCreate) -> StrategyRuntimeAssessment:
    try:
        return strategy_runtime_orchestrator_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-strategy-runtime/assessments", response_model=list[StrategyRuntimeAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[StrategyRuntimeAssessment]:
    return strategy_runtime_orchestrator_service.list_records(workspace_id)


@router.get("/v1/executive-mt5-strategy-runtime/assessments/{record_id}", response_model=StrategyRuntimeAssessment)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> StrategyRuntimeAssessment:
    record = strategy_runtime_orchestrator_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Strategy runtime assessment not found")
    return record


@router.post("/v1/executive-mt5-strategy-runtime/assessments/{record_id}/execute", response_model=StrategyRuntimeAssessment)
def execute_assessment(record_id: UUID, request: StrategyRuntimeExecuteRequest, workspace_id: str = Query(min_length=1, max_length=100)) -> StrategyRuntimeAssessment:
    try:
        return strategy_runtime_orchestrator_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-strategy-runtime/audit", response_model=list[AuditRecord])
def audit_records(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return strategy_runtime_orchestrator_service.audit_records(workspace_id)
