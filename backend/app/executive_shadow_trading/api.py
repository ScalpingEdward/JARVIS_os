from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    ExperimentCreate,
    ExperimentListResponse,
    ExperimentStatusUpdate,
    ShadowTrade,
    ShadowTradeCreate,
    ShadowTradeListResponse,
    ShadowTradeResult,
    ShadowTradingStatusResponse,
    StrategyExperiment,
)
from .service import executive_shadow_trading_service

router = APIRouter(tags=["executive-shadow-trading"])


@router.get("/v1/executive-shadow-trading/status", response_model=ShadowTradingStatusResponse)
def shadow_trading_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ShadowTradingStatusResponse:
    return executive_shadow_trading_service.status(workspace_id)


@router.post("/v1/executive-shadow-trading/experiments", response_model=StrategyExperiment, status_code=status.HTTP_201_CREATED)
def create_experiment(payload: ExperimentCreate) -> StrategyExperiment:
    try:
        return executive_shadow_trading_service.create_experiment(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-shadow-trading/experiments", response_model=ExperimentListResponse)
def list_experiments(workspace_id: str = Query(min_length=1, max_length=100)) -> ExperimentListResponse:
    items = executive_shadow_trading_service.list_experiments(workspace_id)
    return ExperimentListResponse(items=items, count=len(items))


@router.get("/v1/executive-shadow-trading/experiments/{experiment_id}", response_model=StrategyExperiment)
def get_experiment(experiment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> StrategyExperiment:
    item = executive_shadow_trading_service.get_experiment(experiment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Shadow-trading experiment not found")
    return item


@router.post("/v1/executive-shadow-trading/experiments/{experiment_id}/status", response_model=StrategyExperiment)
def update_experiment_status(experiment_id: UUID, payload: ExperimentStatusUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> StrategyExperiment:
    try:
        return executive_shadow_trading_service.update_status(experiment_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/v1/executive-shadow-trading/trades", response_model=ShadowTrade, status_code=status.HTTP_201_CREATED)
def create_shadow_trade(payload: ShadowTradeCreate) -> ShadowTrade:
    try:
        return executive_shadow_trading_service.create_trade(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-shadow-trading/trades", response_model=ShadowTradeListResponse)
def list_shadow_trades(workspace_id: str = Query(min_length=1, max_length=100), experiment_id: UUID | None = None) -> ShadowTradeListResponse:
    items = executive_shadow_trading_service.list_trades(workspace_id, experiment_id)
    return ShadowTradeListResponse(items=items, count=len(items))


@router.post("/v1/executive-shadow-trading/trades/{trade_id}/resolve", response_model=ShadowTrade)
def resolve_shadow_trade(trade_id: UUID, payload: ShadowTradeResult, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ShadowTrade:
    try:
        return executive_shadow_trading_service.resolve_trade(trade_id, workspace_id, payload, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-shadow-trading/audit", response_model=list[AuditRecord])
def shadow_trading_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_shadow_trading_service.audit_records(workspace_id)
