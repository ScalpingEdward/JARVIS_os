from fastapi import APIRouter, HTTPException

from .analysis import AnalysisError
from .models import ReasonIn, WatchItem, Watchlist, WatchlistIn
from .service import watchlist_service

router = APIRouter(prefix="/v1/watchlist", tags=["watchlist"])


@router.post("/snapshot", response_model=Watchlist)
def push_snapshot(payload: WatchlistIn) -> Watchlist:
    """Called by the market feed once a minute."""
    return watchlist_service.push(payload)


@router.get("", response_model=Watchlist)
def get_watchlist() -> Watchlist:
    return watchlist_service.get()


@router.put("/reasons/{name}", response_model=WatchItem)
def set_reason(name: str, payload: ReasonIn) -> WatchItem:
    """Why someone recommended this symbol, and who."""
    try:
        return watchlist_service.set_reason(name, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"{name!r} is not on the watchlist")


@router.post("/analyse/{name}", response_model=WatchItem)
def analyse(name: str) -> WatchItem:
    """AURON's short read on the symbol (Claude). Observation, not advice."""
    try:
        return watchlist_service.analyse(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"{name!r} is not on the watchlist")
    except AnalysisError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
