from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AssetClass(str, Enum):
    forex = "forex"
    commodity = "commodity"
    index = "index"
    crypto = "crypto"
    equity = "equity"


class MarketRegime(str, Enum):
    trending = "trending"
    ranging = "ranging"
    volatile = "volatile"
    compression = "compression"
    transition = "transition"
    unknown = "unknown"


class Direction(str, Enum):
    bullish = "bullish"
    bearish = "bearish"
    neutral = "neutral"


class TimeframeSignal(BaseModel):
    timeframe: str = Field(min_length=1, max_length=12)
    direction: Direction = Direction.neutral
    structure_score: float = Field(default=0.5, ge=0, le=1)
    liquidity_score: float = Field(default=0.5, ge=0, le=1)
    volatility_score: float = Field(default=0.5, ge=0, le=1)


class MacroEvent(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    impact: float = Field(ge=0, le=1)
    affected_symbols: list[str] = Field(default_factory=list)
    scheduled_at: datetime


class CorrelationInput(BaseModel):
    symbol: str = Field(min_length=1, max_length=30)
    coefficient: float = Field(ge=-1, le=1)


class MarketSnapshotCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=30)
    asset_class: AssetClass
    priority: int = Field(default=3, ge=1, le=5)
    timeframes: list[TimeframeSignal] = Field(default_factory=list)
    correlations: list[CorrelationInput] = Field(default_factory=list)
    macro_events: list[MacroEvent] = Field(default_factory=list)
    spread_score: float = Field(default=0.5, ge=0, le=1)
    session_liquidity: float = Field(default=0.5, ge=0, le=1)


class MarketSnapshot(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    symbol: str
    asset_class: AssetClass
    priority: int
    regime: MarketRegime
    bias: Direction
    confidence: float = Field(ge=0, le=1)
    risk_score: float = Field(ge=0, le=1)
    opportunity_score: float = Field(ge=0, le=1)
    timeframes: list[TimeframeSignal]
    correlations: list[CorrelationInput]
    macro_events: list[MacroEvent]
    rationale: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    automatic_order_execution: bool = False


class WatchlistItem(BaseModel):
    symbol: str
    priority: int
    opportunity_score: float
    risk_score: float
    regime: MarketRegime
    bias: Direction


class IntelligenceStatus(BaseModel):
    total_snapshots: int
    tracked_symbols: int
    high_priority: int
    elevated_risk: int
    automatic_order_execution: bool = False
    automatic_merge: bool = False


class SnapshotList(BaseModel):
    items: list[MarketSnapshot]
    count: int
