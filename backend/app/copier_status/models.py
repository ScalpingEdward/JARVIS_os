from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class CopierGroup(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    pnl_today: float = 0
    pnl_week: float = 0
    pnl_total: float = 0
    closed_trades: int = Field(default=0, ge=0)
    open_positions: int = Field(default=0, ge=0)
    open_pnl: float = 0


class CopierPosition(BaseModel):
    ticket: int
    symbol: str
    side: str
    volume: float
    price_open: float
    sl: float = 0
    tp: float = 0
    profit: float = 0
    group: str


class CopierClosedTrade(BaseModel):
    position: int
    group: str
    symbol: str = ""
    side: str = ""
    volume: float = 0
    price_open: float = 0
    price_close: float = 0
    opened: float | None = None   # UTC epoch seconds
    closed: float
    comment: str = ""             # MT5's, e.g. "[tp 4182.0]" or "[sl 4150.0]"
    profit: float                 # after commission and swap


class CopierStatusIn(BaseModel):
    """Exactly what signal_copier/report.py sends."""

    profile: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,39}$")
    account_login: int = Field(gt=0)
    server: str = Field(min_length=1, max_length=150)
    currency: str = Field(min_length=1, max_length=10)
    balance: float
    equity: float
    captured_at: datetime
    groups: list[CopierGroup] = Field(default_factory=list)
    open_positions: list[CopierPosition] = Field(default_factory=list)
    label: str | None = Field(default=None, max_length=100)  # display name, e.g. the group's
    closed: list[CopierClosedTrade] = Field(default_factory=list, max_length=500)  # newest first
    halt_reason: str = Field(default="", max_length=300)  # paused by Brano / loss stop; "" = trading


class CopierState(StrEnum):
    live = "live"        # pushed within the last 3 minutes
    stale = "stale"      # a push or two missed
    offline = "offline"  # the copier or its machine is not running


class CopierStatus(CopierStatusIn):
    received_at: datetime
    state: CopierState
    commands: list[dict] = Field(default_factory=list)  # for the copier: pause / resume / close_all to run now


class CopierTotals(BaseModel):
    """One per currency: a EUR account and a USD cent account do not add up."""

    currency: str
    accounts: int
    balance: float
    equity: float
    pnl_today: float
    pnl_week: float
    pnl_total: float
    open_pnl: float
    open_positions: int


class CopierGroupTotal(CopierGroup):
    currency: str
    accounts: list[str] = Field(default_factory=list)  # profiles following this group


class CopierOverview(BaseModel):
    totals: list[CopierTotals]
    accounts: list[CopierStatus]
    groups: list[CopierGroupTotal]


class CopierEquityPoint(BaseModel):
    at: datetime
    balance: float
    equity: float
