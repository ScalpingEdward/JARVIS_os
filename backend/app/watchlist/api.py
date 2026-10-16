from fastapi import APIRouter

from .models import Watchlist, WatchlistIn
from .service import watchlist_service

router = APIRouter(prefix="/v1/watchlist", tags=["watchlist"])


@router.post("/snapshot", response_model=Watchlist)
def push_snapshot(payload: WatchlistIn) -> Watchlist:
    """Called by the market feed once a minute."""
    return watchlist_service.push(payload)


@router.get("", response_model=Watchlist)
def get_watchlist() -> Watchlist:
    return watchlist_service.get()
