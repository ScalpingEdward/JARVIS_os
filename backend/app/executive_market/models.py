from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class SignalType(str, Enum):
    demand = "demand"
    competitor = "competitor"
    regulatory = "regulatory"
    technology = "technology"
    customer = "customer"


class SignalDirection(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class MarketSegment(BaseModel):
    segment_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    market_size: float = Field(ge=0)
    growth_rate: float = Field(ge=-100, le=1000)
    attractiveness: float = Field(ge=0, le=100)
    current_share: float = Field(ge=0, le=100)
    target_share: float = Field(ge=0, le=100)


class CompetitorProfile(BaseModel):
    competitor_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    relative_strength: float = Field(ge=0, le=100)
    innovation_velocity: float = Field(ge=0, le=100)
    price_pressure: float = Field(ge=0, le=100)
    strategic_threat: float = Field(ge=0, le=100)


class MarketSignal(BaseModel):
    signal_id: str = Field(min_length=1, max_length=100)
    signal_type: SignalType
    direction: SignalDirection
    confidence: float = Field(ge=0, le=100)
    impact: float = Field(ge=0, le=100)
    description: str = Field(min_length=1, max_length=500)


class MarketPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=100)
    strategy_plan_id: UUID | None = None
    capital_portfolio_id: UUID | None = None
    talent_portfolio_id: UUID | None = None
    segments: list[MarketSegment] = Field(min_length=1)
    competitors: list[CompetitorProfile] = Field(default_factory=list)
    signals: list[MarketSignal] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_ids(self):
        for values, label in ((self.segments, "segment"), (self.competitors, "competitor"), (self.signals, "signal")):
            ids = [getattr(value, f"{label}_id") for value in values]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {label} id")
        return self


class SignalUpdate(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    signal_id: str = Field(min_length=1, max_length=100)
    confidence: float | None = Field(default=None, ge=0, le=100)
    impact: float | None = Field(default=None, ge=0, le=100)
    direction: SignalDirection | None = None


class ExecutiveMarketPortfolio(MarketPortfolioCreate):
    portfolio_id: UUID = Field(default_factory=uuid4)
    opportunity_score: float = 0
    threat_score: float = 0
    positioning_score: float = 0
    weighted_growth_rate: float = 0
    whitespace_segments: list[str] = Field(default_factory=list)
    high_threat_competitors: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    assessed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    autonomous_actions_enabled: bool = False


class MarketListResponse(BaseModel):
    items: list[ExecutiveMarketPortfolio]
    count: int


class MarketStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    assessed_portfolios: int
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    actor_id: str
    action: str
    portfolio_id: UUID
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
