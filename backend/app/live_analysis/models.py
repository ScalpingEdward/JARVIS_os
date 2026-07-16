from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Bias(StrEnum):
    bullish = "bullish"
    bearish = "bearish"
    neutral = "neutral"


class Decision(StrEnum):
    valid = "valid"
    watch = "watch"
    rejected = "rejected"


class MarketContext(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(min_length=1, max_length=8)
    higher_timeframe_bias: Bias = Bias.neutral
    tradingview_alert_id: UUID | None = None
    mt5_terminal_id: UUID | None = None
    vision_analysis_id: UUID | None = None
    liquidity_sweep: bool = False
    structure_shift: bool = False
    fair_value_gap: bool = False
    order_block: bool = False
    premium_discount_aligned: bool = False
    risk_reward: float = Field(default=0, ge=0, le=20)
    spread_points: float = Field(default=0, ge=0)
    news_minutes: int | None = Field(default=None, ge=0)
    daily_drawdown_percent: float = Field(default=0, ge=0, le=100)
    open_trades: int = Field(default=0, ge=0)


class PersonalStats(BaseModel):
    sample_size: int = Field(default=0, ge=0)
    win_rate: float = Field(default=0, ge=0, le=100)
    average_rr: float = Field(default=0, ge=0)
    matching_setup_win_rate: float | None = Field(default=None, ge=0, le=100)


class LiveAnalysisRequest(BaseModel):
    context: MarketContext
    personal_stats: PersonalStats = Field(default_factory=PersonalStats)
    max_spread_points: float = Field(default=40, ge=0)
    max_daily_drawdown_percent: float = Field(default=4, ge=0, le=100)
    max_open_trades: int = Field(default=3, ge=0)
    minimum_rr: float = Field(default=2, ge=0)
    news_block_minutes: int = Field(default=15, ge=0)


class LiveAnalysisRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    symbol: str
    timeframe: str
    decision: Decision
    score: int = Field(ge=0, le=100)
    confidence_percent: int = Field(ge=0, le=100)
    blockers: list[str] = Field(default_factory=list)
    confirmations: list[str] = Field(default_factory=list)
    personal_adjustment: int = Field(default=0, ge=-20, le=20)
    advisory_only: bool = True
    human_approval_required: bool = True
    automatic_order_execution: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LiveAnalysisStatus(BaseModel):
    analyses: int
    valid: int
    watch: int
    rejected: int
    mt5_ready: bool = True
    tradingview_ready: bool = True
    vision_ready: bool = True
    automatic_order_execution: bool = False
