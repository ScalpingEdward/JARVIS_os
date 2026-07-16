from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class VisualSource(str, Enum):
    tradingview = "tradingview"
    mt5 = "mt5"
    footprint = "footprint"
    dom = "dom"
    heatmap = "heatmap"
    document = "document"
    other = "other"


class VisualBias(str, Enum):
    bullish = "bullish"
    bearish = "bearish"
    neutral = "neutral"
    mixed = "mixed"
    insufficient_data = "insufficient_data"


class StructureType(str, Enum):
    bos = "bos"
    choch = "choch"
    liquidity_sweep = "liquidity_sweep"
    fvg = "fvg"
    order_block = "order_block"
    support = "support"
    resistance = "resistance"
    trendline = "trendline"
    imbalance = "imbalance"
    absorption = "absorption"
    volume_node = "volume_node"


class VisualRegion(BaseModel):
    kind: StructureType
    label: str = Field(min_length=1, max_length=160)
    price_low: float | None = None
    price_high: float | None = None
    direction: VisualBias = VisualBias.neutral
    confidence: float = Field(default=0.5, ge=0, le=1)
    evidence: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def validate_price_range(self):
        if self.price_low is not None and self.price_high is not None and self.price_low > self.price_high:
            raise ValueError("price_low cannot exceed price_high")
        return self


class ChartObservation(BaseModel):
    source: VisualSource
    image_ref: str = Field(min_length=1, max_length=1000)
    timeframe: str = Field(min_length=1, max_length=20)
    image_quality: float = Field(default=0.7, ge=0, le=1)
    detected_symbol: str | None = Field(default=None, max_length=40)
    detected_bias: VisualBias = VisualBias.insufficient_data
    regions: list[VisualRegion] = Field(default_factory=list)
    visible_indicators: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MarketVisionCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    observations: list[ChartObservation] = Field(min_length=1, max_length=12)
    market_bias: VisualBias | None = None
    orderflow_bias: VisualBias | None = None
    market_confidence: float | None = Field(default=None, ge=0, le=1)
    orderflow_confidence: float | None = Field(default=None, ge=0, le=1)
    current_price: float | None = None


class MarketVisionRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    symbol: str
    observations: list[ChartObservation]
    visual_bias: VisualBias
    multi_timeframe_alignment: float = Field(ge=0, le=1)
    structured_data_alignment: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    detected_regions: list[VisualRegion] = Field(default_factory=list)
    confirmations: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MarketVisionListResponse(BaseModel):
    items: list[MarketVisionRecord]
    count: int


class MarketVisionStatus(BaseModel):
    analyses: int
    symbols: int
    bullish: int
    bearish: int
    mixed_or_neutral: int
    automatic_order_execution: bool = False
    automatic_merge: bool = False
