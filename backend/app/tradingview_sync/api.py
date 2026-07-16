from fastapi import APIRouter, HTTPException

from .models import ChartFrame, ChartFrameCreate, SyncStatus, TradingViewAlert, TradingViewWebhook, WatchlistCreate, WatchlistRecord
from .service import TradingViewSyncError, tradingview_sync_service

router = APIRouter(prefix="/v1/tradingview", tags=["tradingview"])


@router.get("/status", response_model=SyncStatus)
def status() -> SyncStatus:
    return tradingview_sync_service.status()


@router.post("/watchlists", response_model=WatchlistRecord)
def create_watchlist(payload: WatchlistCreate) -> WatchlistRecord:
    return tradingview_sync_service.create_watchlist(payload)


@router.get("/watchlists", response_model=list[WatchlistRecord])
def list_watchlists() -> list[WatchlistRecord]:
    return tradingview_sync_service.list_watchlists()


@router.post("/webhook", response_model=TradingViewAlert)
def receive_webhook(payload: TradingViewWebhook) -> TradingViewAlert:
    try:
        return tradingview_sync_service.receive_webhook(payload)
    except TradingViewSyncError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/alerts", response_model=list[TradingViewAlert])
def list_alerts() -> list[TradingViewAlert]:
    return tradingview_sync_service.list_alerts()


@router.post("/frames", response_model=ChartFrame)
def add_frame(payload: ChartFrameCreate) -> ChartFrame:
    return tradingview_sync_service.add_frame(payload)


@router.get("/frames", response_model=list[ChartFrame])
def list_frames() -> list[ChartFrame]:
    return tradingview_sync_service.list_frames()
