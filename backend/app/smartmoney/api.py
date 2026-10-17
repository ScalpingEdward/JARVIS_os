from fastapi import APIRouter

from .service import smart_money_service

router = APIRouter(prefix="/v1/smartmoney", tags=["smart-money"])


@router.get("")
def overview() -> dict:
    """The week's high-impact macro dates, insider trades on the watchlist (30 days), and clusters."""
    return smart_money_service.overview()


@router.post("/poll")
def poll() -> dict:
    """Fetch new Form 4 filings now instead of waiting for the next round."""
    return smart_money_service.poll_insiders()
