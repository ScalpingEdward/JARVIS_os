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


@router.post("/backtest")
def save_backtest(payload: dict) -> dict:
    """Written by tools/insider_backtest.py on the laptop (it needs MT5 for the prices)."""
    return smart_money_service.save_backtest(payload)


@router.get("/backtest")
def backtest(ticker: str | None = None) -> dict:
    """The latest backtest summary; with ?ticker= also that company's events."""
    bt = smart_money_service.backtest()
    if not bt:
        return {"available": False}
    out = {"available": True, "generated_at": bt["generated_at"], "quarters": bt.get("quarters", []), "summary": bt["summary"]}
    if ticker:
        out["events"] = [e for e in bt["events"] if e["ticker"] == ticker.upper()]
    return out
