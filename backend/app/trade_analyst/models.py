from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class TradeDirection(str, Enum):
    long = "long"
    short = "short"
    neutral = "neutral"


class AnalystVerdict(str, Enum):
    favorable = "favorable"
    conditional = "conditional"
    avoid = "avoid"
    insufficient_data = "insufficient_data"


class RiskLevel(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"
    extreme = "extreme"


class PriceZone(BaseModel):
    low: float
    high: float

    @model_validator(mode="after")
    def validate_order(self):
        if self.low > self.high:
            raise ValueError("Price zone low must not exceed high")
        return self


class AnalysisFactor(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    score: float = Field(ge=-1, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class TradeAnalysisCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    direction: TradeDirection
    current_price: float = Field(gt=0)
    entry_zone: PriceZone | None = None
    invalidation_price: float | None = Field(default=None, gt=0)
    target_prices: list[float] = Field(default_factory=list)
    market_regime: str | None = Field(default=None, max_length=80)
    higher_timeframe_bias: TradeDirection = TradeDirection.neutral
    structure_score: float = Field(default=0, ge=-1, le=1)
    liquidity_score: float = Field(default=0, ge=-1, le=1)
    orderflow_score: float = Field(default=0, ge=-1, le=1)
    macro_risk: float = Field(default=0, ge=0, le=1)
    correlation_risk: float = Field(default=0, ge=0, le=1)
    data_quality: float = Field(default=0.5, ge=0, le=1)
    memory_edge: float = Field(default=0, ge=-1, le=1)
    simulation_probability: float | None = Field(default=None, ge=0, le=1)
    factors: list[AnalysisFactor] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TradeAnalysisRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    symbol: str
    direction: TradeDirection
    verdict: AnalystVerdict
    confidence: float = Field(ge=0, le=1)
    risk_level: RiskLevel
    composite_score: float = Field(ge=-1, le=1)
    current_price: float
    entry_zone: PriceZone | None
    invalidation_price: float | None
    target_prices: list[float]
    risk_reward: float | None = None
    supporting_factors: list[str] = Field(default_factory=list)
    opposing_factors: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    primary_scenario: str
    alternative_scenario: str
    invalidation_reason: str
    data_quality: float
    advisory_only: bool = True
    automatic_order_execution: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TradeAnalysisListResponse(BaseModel):
    items: list[TradeAnalysisRecord]
    count: int


class TradeAnalystStatus(BaseModel):
    analyses: int
    favorable: int
    conditional: int
    avoid: int
    insufficient_data: int
    average_confidence: float
    automatic_order_execution: bool = False
    automatic_merge: bool = False
