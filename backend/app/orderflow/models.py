from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class OrderflowSource(str, Enum):
    broker = "broker"
    futures_exchange = "futures_exchange"
    crypto_exchange = "crypto_exchange"
    third_party = "third_party"
    manual = "manual"


class OrderflowSignal(str, Enum):
    bullish = "bullish"
    bearish = "bearish"
    neutral = "neutral"
    absorption_buy = "absorption_buy"
    absorption_sell = "absorption_sell"
    exhaustion_buy = "exhaustion_buy"
    exhaustion_sell = "exhaustion_sell"


class PriceLevel(BaseModel):
    price: float
    bid_volume: float = Field(default=0, ge=0)
    ask_volume: float = Field(default=0, ge=0)
    resting_bid: float = Field(default=0, ge=0)
    resting_ask: float = Field(default=0, ge=0)

    @property
    def delta(self) -> float:
        return self.ask_volume - self.bid_volume


class VolumeProfile(BaseModel):
    poc: float | None = None
    value_area_high: float | None = None
    value_area_low: float | None = None
    high_volume_nodes: list[float] = Field(default_factory=list)
    low_volume_nodes: list[float] = Field(default_factory=list)


class OrderflowSnapshotCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=30)
    timeframe: str = Field(default="1m", min_length=1, max_length=10)
    source: OrderflowSource
    levels: list[PriceLevel] = Field(default_factory=list, max_length=5000)
    volume_profile: VolumeProfile = Field(default_factory=VolumeProfile)
    cumulative_delta: float = 0
    open_interest: float | None = Field(default=None, ge=0)
    previous_open_interest: float | None = Field(default=None, ge=0)
    session: str | None = Field(default=None, max_length=40)
    source_timestamp: datetime | None = None

    @model_validator(mode="after")
    def require_data(self):
        if not self.levels and self.open_interest is None:
            raise ValueError("At least price levels or open interest are required")
        return self


class OrderflowSnapshot(OrderflowSnapshotCreate):
    id: UUID = Field(default_factory=uuid4)
    total_bid_volume: float = 0
    total_ask_volume: float = 0
    delta: float = 0
    delta_percent: float = 0
    open_interest_change: float | None = None
    stacked_buy_imbalances: list[float] = Field(default_factory=list)
    stacked_sell_imbalances: list[float] = Field(default_factory=list)
    absorption_levels: list[float] = Field(default_factory=list)
    liquidity_levels: list[float] = Field(default_factory=list)
    signal: OrderflowSignal = OrderflowSignal.neutral
    confidence: float = Field(default=0, ge=0, le=1)
    data_quality: float = Field(default=0, ge=0, le=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrderflowSnapshotList(BaseModel):
    items: list[OrderflowSnapshot]
    count: int


class OrderflowStatus(BaseModel):
    symbols: int
    snapshots: int
    bullish: int
    bearish: int
    neutral: int
    automatic_order_execution: bool = False
    automatic_merge: bool = False
