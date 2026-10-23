import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .models import CopierEquityPoint, CopierOverview, CopierStatus, CopierStatusIn
from . import commands
from .service import CopierStatusError, copier_status_service

router = APIRouter(prefix="/v1/copier", tags=["copier"])


@router.post("/status", response_model=CopierStatus)
def push_status(payload: CopierStatusIn) -> CopierStatus:
    """Called by each copier profile every 15 seconds; the answer carries its pending commands."""
    st = copier_status_service.push(payload)
    st.commands = commands.pending_for(payload.profile)
    from app.notification_hub import mute
    from app.push import service as push
    st.telegram_quiet = mute.trades_quiet() or bool(push.devices() and not push.wants("trades", "telegram"))
    return st


class LivePosition(BaseModel):
    ticket: int
    profit: float


class LiveIn(BaseModel):
    profile: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,39}$")
    balance: float
    equity: float
    positions: list[LivePosition] = Field(default_factory=list, max_length=500)


# second-by-second numbers live in memory only: a rebuild loses a few seconds, nothing more
_live: dict[str, tuple[float, LiveIn]] = {}
LIVE_FOR_S = 10   # older than this: the copier has stopped sending, the 15 s report counts again


@router.post("/live")
def push_live(payload: LiveIn) -> dict:
    """Every second from each copier: balance, equity, each open position's profit. The answer names
    the symbols whose chart is open on a dashboard -- the copier then sends their candles (/rates)."""
    _live[payload.profile] = (time.monotonic(), payload)
    now = time.monotonic()
    return {"want_rates": sorted({sym for (prof, sym), at in list(_chart_wanted.items())
                                  if prof == payload.profile and now - at <= CHART_FOR_S}),
            "want_hist": [h for (prof, _k), (at, h) in list(_hist_wanted.items()) if prof == payload.profile and now - at <= 60],
            "want_quote": [q for (prof, _k), (at, q) in list(_quote_wanted.items()) if prof == payload.profile and now - at <= 20],
            "commands_waiting": commands.wake(payload.profile)}


# ---- a position's chart (dashboard click) -- five-minute candles straight from the copier's MT5 ----
_chart_wanted: dict[tuple[str, str], float] = {}     # (profile, symbol) -> last asked
_rates: dict[tuple[str, str], tuple[float, list, str | None]] = {}
CHART_FOR_S = 30   # a closed chart: the copier stops sending after this
# past stretches for AURON's trade review (review.py): asked once, the copier sends each once
_hist_wanted: dict[tuple[str, str], tuple[float, dict]] = {}


def want_hist(profile: str, symbol: str, start: float, end: float, tf: str = "M5") -> str:
    key = f"{symbol}@{tf}@{int(start)}-{int(end)}"
    if (profile, key) not in _rates:
        _hist_wanted[(profile, key)] = (time.monotonic(), {"key": key, "symbol": symbol, "tf": tf, "from": start, "to": end})
    return key


# a trade AURON prepares (tickets.py): the copier sends price and contract data for the key
_quote_wanted: dict[tuple[str, str], tuple[float, dict]] = {}
_quotes: dict[tuple[str, str], dict] = {}


def want_quote(profile: str, symbol: str) -> str:
    key = f"q{time.monotonic_ns()}"
    _quote_wanted[(profile, key)] = (time.monotonic(), {"key": key, "symbol": symbol})
    return key


def quote_for(profile: str, key: str) -> dict | None:
    got = _quotes.pop((profile, key), None)
    if got:
        _quote_wanted.pop((profile, key), None)
    return got


@router.post("/quote", status_code=204)
def push_quote(payload: dict) -> None:
    prof, key = str(payload.get("profile", "")), str(payload.get("key", ""))
    if (prof, key) in _quote_wanted:
        _quotes[(prof, key)] = payload


def hist(profile: str, key: str) -> list | None:
    got = _rates.get((profile, key))
    if got:
        _hist_wanted.pop((profile, key), None)
    return got[1] if got else None
TIMEFRAMES = ("M1", "M5", "M15", "H1", "H4", "D1")   # the chart's buttons (Brano, 2026-10-22)


def _key(symbol: str, tf: str) -> str:
    return symbol if tf == "M5" else f"{symbol}@{tf}"


class RatesIn(BaseModel):
    profile: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,39}$")
    symbol: str = Field(min_length=1, max_length=120)
    bars: list[list[float]] = Field(default_factory=list, max_length=6000)
    name: str | None = Field(default=None, max_length=40)   # the broker's spelling it found (XAUUSD -> XAUUSD.s)


@router.post("/rates", status_code=204)
def push_rates(payload: RatesIn) -> None:
    _rates[(payload.profile, payload.symbol)] = (time.monotonic(), payload.bars, payload.name)


@router.get("/chart")
def chart(profile: str, symbol: str, tf: str = "M5") -> dict:
    """The dashboard asks every 2 s while the chart is open; the first ask starts the copier sending."""
    if tf not in TIMEFRAMES:
        raise HTTPException(status_code=422, detail=f"timeframe {tf!r}; es gibt {list(TIMEFRAMES)}")
    key = _key(symbol, tf)
    _chart_wanted[(profile, key)] = time.monotonic()
    got = _rates.get((profile, key))
    if not got:
        return {"bars": [], "pending": True}
    return {"bars": got[1], "name": got[2], "age_s": round(time.monotonic() - got[0], 1)}


@router.get("/live")
def live() -> dict:
    """{profile: {balance, equity, positions: {ticket: profit}, age_s}} -- only fresh ones."""
    now = time.monotonic()
    return {p: {"balance": v.balance, "equity": v.equity, "positions": {str(x.ticket): x.profit for x in v.positions},
                "age_s": round(now - at, 1)}
            for p, (at, v) in list(_live.items()) if now - at <= LIVE_FOR_S}


@router.get("/status", response_model=list[CopierStatus])
def list_status() -> list[CopierStatus]:
    return copier_status_service.list()


@router.get("/overview", response_model=CopierOverview)
def overview() -> CopierOverview:
    """Totals per currency, every account, and every group across accounts."""
    return copier_status_service.overview()


@router.get("/history", response_model=dict[str, list[CopierEquityPoint]])
def history(hours: float = 24) -> dict[str, list[CopierEquityPoint]]:
    """Balance and equity per profile, one point every five minutes -- for the dashboard's curves."""
    return copier_status_service.history(min(max(hours, 1), 24 * 30))


@router.delete("/status/{profile}", status_code=204)
def forget(profile: str) -> None:
    """Drop a profile that no longer exists. Nothing in MT5 is touched."""
    try:
        copier_status_service.forget(profile)
    except CopierStatusError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class CommandIn(BaseModel):
    profile: str
    action: str
    confirmed: bool = False   # the dashboard sets it after its own confirmation dialog


@router.post("/commands")
def create_command(payload: CommandIn) -> dict:
    """pause / resume run with the next push; close_all waits for a confirmation unless confirmed."""
    try:
        return commands.create(payload.profile, payload.action, "dashboard", payload.confirmed)
    except commands.CommandError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/commands")
def list_commands() -> list[dict]:
    return commands.recent()


@router.post("/commands/{command_id}/confirm")
def confirm_command(command_id: str) -> dict:
    try:
        return commands.confirm(command_id)
    except commands.CommandError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/commands/{command_id}/cancel")
def cancel_command(command_id: str) -> dict:
    try:
        return commands.cancel(command_id)
    except commands.CommandError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class DoneIn(BaseModel):
    ok: bool
    result: str = ""


@router.post("/commands/{command_id}/done")
def command_done(command_id: str, payload: DoneIn) -> dict:
    """The copier acks a command it ran."""
    try:
        return commands.done(command_id, payload.ok, payload.result)
    except commands.CommandError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---- a trade AURON prepared (tickets.py): the card on the dashboard shows it, Brano's click opens it ----
@router.get("/tickets/active")
def ticket_active() -> dict:
    from . import tickets
    return {"ticket": tickets.active()}


@router.post("/tickets/open")
def ticket_open() -> dict:
    """Brano's click on the ticket card."""
    from . import tickets
    try:
        return tickets.open_ticket("click")
    except tickets.TicketError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/tickets/cancel")
def ticket_cancel() -> dict:
    from . import tickets
    try:
        return tickets.cancel()
    except tickets.TicketError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
