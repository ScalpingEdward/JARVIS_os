from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SyncSource(StrEnum):
    webhook = "webhook"
    screenshot = "screenshot"
    browser = "browser"


class AlertDirection(StrEnum):
    long = "long"
    short = "short"
    neutral = "neutral"


class WatchItem(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    timeframe: str = Field(min_length=1, max_length=10)
    mt5_terminal_id: UUID | None = None
    enabled: bool = True


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    items: list[WatchItem] = Field(default_factory=list, max_length=100)


class WatchlistRecord(WatchlistCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TradingViewWebhook(BaseModel):
    secret: str = Field(min_length=8, max_length=200)
    symbol: str = Field(min_length=1, max_length=40)
    timeframe: str = Field(min_length=1, max_length=10)
    price: float
    direction: AlertDirection = AlertDirection.neutral
    alert_name: str = Field(min_length=1, max_length=200)
    zone_low: float | None = None
    zone_high: float | None = None
    message: str = Field(default="", max_length=2000)


class TradingViewAlert(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    symbol: str
    timeframe: str
    price: float
    direction: AlertDirection
    alert_name: str
    zone_low: float | None = None
    zone_high: float | None = None
    message: str = ""
    source: SyncSource = SyncSource.webhook
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    order_execution_enabled: bool = False


class ChartFrameCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    timeframe: str = Field(min_length=1, max_length=10)
    image_ref: str = Field(min_length=1, max_length=1000)
    monitor: int = Field(default=1, ge=1, le=8)


class ChartFrame(ChartFrameCreate):
    id: UUID = Field(default_factory=uuid4)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SyncStatus(BaseModel):
    watchlists: int
    watch_items: int
    alerts: int
    frames: int
    mt5_sync_enabled: bool = True
    automatic_order_execution: bool = False
