from datetime import datetime

from pydantic import BaseModel, Field


class WatchItem(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    symbol: str | None = Field(default=None, max_length=40)   # None: no data source yet
    category: str = Field(min_length=1, max_length=40)
    top: int | None = Field(default=None, ge=1, le=10)        # position on the dashboard card
    price: float | None = None
    change_pct: float | None = None
    high_52w: float | None = None
    low_52w: float | None = None
    from_high_pct: float | None = None
    sma50: float | None = None
    sma200: float | None = None
    vs_sma50_pct: float | None = None
    vs_sma200_pct: float | None = None
    rsi14: float | None = None
    spark: list[float] = Field(default_factory=list, max_length=60)
    notes: list[str] = Field(default_factory=list, max_length=10)
    quoted_at: datetime | None = None
    # set by Brano and by AURON, not by the feed; merged in on read
    reason: str = ""
    recommended_by: str = ""
    analysis: str = ""
    analysis_at: datetime | None = None


class WatchlistIn(BaseModel):
    items: list[WatchItem] = Field(max_length=300)
    captured_at: datetime


class Watchlist(WatchlistIn):
    received_at: datetime | None = None
    stale: bool = True  # no push for 5 minutes: the feed or its laptop is down


class ReasonIn(BaseModel):
    reason: str = Field(default="", max_length=2000)
    recommended_by: str = Field(default="", max_length=100)
