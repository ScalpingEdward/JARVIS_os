from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .trading_models import (
    TradingDecisionCreate,
    TradingDecisionListResponse,
    TradingDecisionRecord,
    TradingDecisionStatusResponse,
)
from .trading_service import trading_decision_orchestration_service

router = APIRouter(tags=["executive-trading-decisions"])


@router.get("/v1/executive-decisions/trading/status", response_model=TradingDecisionStatusResponse)
def trading_decision_status(workspace_id: str = Query(min_length=1, max_length=100)) -> TradingDecisionStatusResponse:
    return trading_decision_orchestration_service.status(workspace_id)


@router.post("/v1/executive-decisions/trading", response_model=TradingDecisionRecord, status_code=status.HTTP_201_CREATED)
def create_trading_decision(payload: TradingDecisionCreate) -> TradingDecisionRecord:
    try:
        return trading_decision_orchestration_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-decisions/trading", response_model=TradingDecisionListResponse)
def list_trading_decisions(workspace_id: str = Query(min_length=1, max_length=100)) -> TradingDecisionListResponse:
    items = trading_decision_orchestration_service.list_records(workspace_id)
    return TradingDecisionListResponse(items=items, count=len(items))


@router.get("/v1/executive-decisions/trading/{record_id}", response_model=TradingDecisionRecord)
def get_trading_decision(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> TradingDecisionRecord:
    item = trading_decision_orchestration_service.get(record_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive trading decision not found")
    return item
