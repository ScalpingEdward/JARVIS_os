from fastapi import APIRouter, HTTPException

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


@router.get("/signalers")
def signalers(verdict: str | None = None, limit: int = 300) -> dict:
    """Every insider as a signal source: buys taken long, sales taken short, 60 trading days, after costs.
    verdict: profi / weg / offen. Plus the walk-forward test: following only proven insiders, no hindsight."""
    bt = smart_money_service.backtest()
    if not bt or "by_signaler" not in bt["summary"]:
        return {"available": False}
    rows = bt["summary"]["by_signaler"]
    counts = {v: sum(1 for x in rows if x["verdict"] == v) for v in ("profi", "weg", "offen")}
    if verdict:
        rows = [x for x in rows if x["verdict"] == verdict]
    return {"available": True, "generated_at": bt["generated_at"], "quarters": bt.get("quarters", []),
            "counts": counts, "walk_forward": bt["summary"].get("walk_forward"), "strategies": bt["summary"].get("strategies"), "rows": rows[:min(max(limit, 1), 2000)]}


@router.get("/follows")
def follows() -> list[dict]:
    """The insiders on Brano's watch list."""
    return smart_money_service.follows()


@router.post("/follows")
def follow(payload: dict) -> dict:
    """Watch an insider from the signaler list ({"owner": "..."}): new trades of theirs come to Telegram."""
    try:
        return smart_money_service.follow(str(payload.get("owner", "")))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="not in the signaler list") from exc


@router.delete("/follows")
def unfollow(owner: str) -> dict:
    return {"removed": smart_money_service.unfollow(owner)}
