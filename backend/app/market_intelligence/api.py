from fastapi import APIRouter, HTTPException, Query, status

from .models import IntelligenceStatus, MarketSnapshot, MarketSnapshotCreate, SnapshotList, WatchlistItem
from .service import market_intelligence_service

router = APIRouter(prefix="/v1/market-intelligence", tags=["market-intelligence"])


@router.get("/status", response_model=IntelligenceStatus)
def intelligence_status() -> IntelligenceStatus:
    return market_intelligence_service.status()


@router.post("/snapshots", response_model=MarketSnapshot, status_code=status.HTTP_201_CREATED)
def create_snapshot(payload: MarketSnapshotCreate) -> MarketSnapshot:
    return market_intelligence_service.analyze(payload)


@router.get("/snapshots", response_model=SnapshotList)
def list_snapshots() -> SnapshotList:
    items = market_intelligence_service.list_all()
    return SnapshotList(items=items, count=len(items))


@router.get("/snapshots/{symbol}", response_model=MarketSnapshot)
def latest_snapshot(symbol: str) -> MarketSnapshot:
    item = market_intelligence_service.latest(symbol)
    if item is None:
        raise HTTPException(status_code=404, detail="Market snapshot not found")
    return item


@router.get("/watchlist", response_model=list[WatchlistItem])
def ranked_watchlist(limit: int = Query(default=15, ge=1, le=50)) -> list[WatchlistItem]:
    return market_intelligence_service.watchlist(limit=limit)
