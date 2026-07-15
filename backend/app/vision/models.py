from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class VisionSource(StrEnum):
    upload = "upload"
    tradingview = "tradingview"
    mt5 = "mt5"
    desktop = "desktop"
    telegram = "telegram"


class FrameKind(StrEnum):
    screenshot = "screenshot"
    chart = "chart"
    application_error = "application_error"


class MarketBias(StrEnum):
    bullish = "bullish"
    bearish = "bearish"
    neutral = "neutral"
    unknown = "unknown"


class VisionFrameCreate(BaseModel):
    source: VisionSource
    kind: FrameKind = FrameKind.screenshot
    image_ref: str = Field(min_length=1, max_length=2000)
    symbol: str | None = Field(default=None, max_length=40)
    timeframe: str | None = Field(default=None, max_length=20)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class DetectedZone(BaseModel):
    label: str
    lower: float | None = None
    upper: float | None = None
    confidence: float = Field(ge=0, le=1)


class VisionFinding(BaseModel):
    label: str
    detail: str
    confidence: float = Field(ge=0, le=1)


class VisionAnalysis(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    frame: VisionFrameCreate
    provider: str
    summary: str
    bias: MarketBias = MarketBias.unknown
    findings: list[VisionFinding] = Field(default_factory=list)
    zones: list[DetectedZone] = Field(default_factory=list)
    advisory_only: bool = True
    order_execution_allowed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LiveFeedCreate(BaseModel):
    source: VisionSource
    name: str = Field(min_length=1, max_length=100)
    symbol: str | None = Field(default=None, max_length=40)
    timeframe: str | None = Field(default=None, max_length=20)
    minimum_interval_seconds: int = Field(default=5, ge=1, le=3600)


class LiveFeedRecord(LiveFeedCreate):
    id: UUID = Field(default_factory=uuid4)
    enabled: bool = True
    last_frame_at: datetime | None = None
    frame_count: int = 0


class LiveFrameIngest(BaseModel):
    image_ref: str = Field(min_length=1, max_length=2000)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class VisionStatus(BaseModel):
    supported_sources: list[VisionSource]
    live_feeds: int
    analyses: int
    advisory_only: bool = True
    automatic_order_execution: bool = False
