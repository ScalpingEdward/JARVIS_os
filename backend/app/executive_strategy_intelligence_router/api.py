from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    StrategyIntelligenceAudit,
    StrategyIntelligenceStatus,
    StrategyRoutingCreate,
    StrategyRoutingExecuteRequest,
    StrategyRoutingRecord,
)
from .service import strategy_intelligence_router_service

router = APIRouter(tags=["executive-strategy-intelligence-router"])


@router.get("/v1/executive-strategy-intelligence/status", response_model=StrategyIntelligenceStatus)
def strategy_status(workspace_id: str = Query(min_length=1, max_length=100)):
    return strategy_intelligence_router_service.status(workspace_id)


@router.post("/v1/executive-strategy-intelligence/routes", response_model=StrategyRoutingRecord, status_code=status.HTTP_201_CREATED)
def create_route(payload: StrategyRoutingCreate):
    try:
        return strategy_intelligence_router_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-strategy-intelligence/routes", response_model=list[StrategyRoutingRecord])
def list_routes(workspace_id: str = Query(min_length=1, max_length=100)):
    return strategy_intelligence_router_service.list_records(workspace_id)


@router.get("/v1/executive-strategy-intelligence/routes/{record_id}", response_model=StrategyRoutingRecord)
def get_route(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)):
    record = strategy_intelligence_router_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="strategy routing record not found")
    return record


@router.post("/v1/executive-strategy-intelligence/routes/{record_id}/execute", response_model=StrategyRoutingRecord)
def execute_route(record_id: UUID, request: StrategyRoutingExecuteRequest, workspace_id: str = Query(min_length=1, max_length=100)):
    try:
        return strategy_intelligence_router_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-strategy-intelligence/audit", response_model=list[StrategyIntelligenceAudit])
def strategy_audit(workspace_id: str = Query(min_length=1, max_length=100)):
    return strategy_intelligence_router_service.audit_records(workspace_id)
