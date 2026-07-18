from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    ExecutiveStrategyCreate,
    ExecutiveStrategyPlan,
    StrategyAnalysis,
    StrategyListResponse,
    StrategyStatusResponse,
    WhatIfRequest,
)
from .service import executive_strategy_service

router = APIRouter(tags=["executive-strategy"])


@router.get("/v1/executive-strategy/status", response_model=StrategyStatusResponse)
def strategy_status(workspace_id: str = Query(min_length=1, max_length=100)) -> StrategyStatusResponse:
    return executive_strategy_service.status(workspace_id)


@router.post("/v1/executive-strategy/plans", response_model=ExecutiveStrategyPlan, status_code=status.HTTP_201_CREATED)
def create_plan(payload: ExecutiveStrategyCreate) -> ExecutiveStrategyPlan:
    try:
        return executive_strategy_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-strategy/plans", response_model=StrategyListResponse)
def list_plans(workspace_id: str = Query(min_length=1, max_length=100)) -> StrategyListResponse:
    items = executive_strategy_service.list_plans(workspace_id)
    return StrategyListResponse(items=items, count=len(items))


@router.get("/v1/executive-strategy/plans/{plan_id}", response_model=ExecutiveStrategyPlan)
def get_plan(plan_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveStrategyPlan:
    record = executive_strategy_service.get(plan_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Executive strategy plan not found")
    return record


@router.post("/v1/executive-strategy/plans/{plan_id}/analyze", response_model=ExecutiveStrategyPlan)
def analyze_plan(plan_id: UUID, scenario: WhatIfRequest, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveStrategyPlan:
    try:
        return executive_strategy_service.analyze(plan_id, workspace_id, actor_id, scenario)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/v1/executive-strategy/plans/{plan_id}/roadmap", response_model=StrategyAnalysis)
def generate_roadmap(plan_id: UUID, scenario: WhatIfRequest, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> StrategyAnalysis:
    try:
        return executive_strategy_service.roadmap(plan_id, workspace_id, actor_id, scenario)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-strategy/audit", response_model=list[AuditRecord])
def strategy_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_strategy_service.audit_records(workspace_id)
