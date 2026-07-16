from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import TradeAnalysisCreate, TradeAnalysisListResponse, TradeAnalysisRecord, TradeAnalystStatus
from .service import trade_analyst_service

router = APIRouter(prefix="/v1/trade-analyst", tags=["trade-analyst"])


@router.get("/status", response_model=TradeAnalystStatus)
def analyst_status() -> TradeAnalystStatus:
    return trade_analyst_service.status()


@router.post("/analyses", response_model=TradeAnalysisRecord, status_code=status.HTTP_201_CREATED)
def create_analysis(payload: TradeAnalysisCreate) -> TradeAnalysisRecord:
    return trade_analyst_service.create(payload)


@router.get("/analyses", response_model=TradeAnalysisListResponse)
def list_analyses(symbol: str | None = Query(default=None, max_length=40)) -> TradeAnalysisListResponse:
    items = trade_analyst_service.list_all(symbol=symbol)
    return TradeAnalysisListResponse(items=items, count=len(items))


@router.get("/analyses/{analysis_id}", response_model=TradeAnalysisRecord)
def get_analysis(analysis_id: UUID) -> TradeAnalysisRecord:
    record = trade_analyst_service.get(analysis_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Trade analysis not found")
    return record


@router.get("/latest/{symbol}", response_model=TradeAnalysisRecord)
def latest_analysis(symbol: str) -> TradeAnalysisRecord:
    record = trade_analyst_service.latest(symbol)
    if record is None:
        raise HTTPException(status_code=404, detail="No trade analysis found for symbol")
    return record
