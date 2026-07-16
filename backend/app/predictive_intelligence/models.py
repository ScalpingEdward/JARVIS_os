from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MarketRegime(str, Enum):
    trending = "trending"
    ranging = "ranging"
    volatile = "volatile"
    uncertain = "uncertain"


class ScenarioType(str, Enum):
    bullish_continuation = "bullish_continuation"
    liquidity_sweep_reversal = "liquidity_sweep_reversal"
    range_expansion = "range_expansion"
    trend_failure = "trend_failure"
    news_shock = "news_shock"


class MarketSignal(BaseModel):
    symbol: str = Field(min_length=2, max_length=32)
    structure_score: float = Field(ge=0, le=1)
    orderflow_score: float = Field(ge=0, le=1)
    liquidity_score: float = Field(ge=0, le=1)
    volatility_score: float = Field(ge=0, le=1)
    news_risk: float = Field(default=0, ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    regime: MarketRegime = MarketRegime.uncertain


class ForecastRequest(BaseModel):
    signals: list[MarketSignal] = Field(min_length=1, max_length=20)
    horizon_minutes: int = Field(default=240, ge=5, le=10080)


class ScenarioForecast(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    symbol: str
    scenario: ScenarioType
    probability: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    expected_volatility: float = Field(ge=0, le=1)
    risk_score: float = Field(ge=0, le=1)
    rationale: list[str]


class OpportunityScore(BaseModel):
    symbol: str
    score: float = Field(ge=0, le=100)
    edge: float = Field(ge=0, le=1)
    risk_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    rank: int = Field(ge=1)


class ExecutionStep(BaseModel):
    order: int = Field(ge=1)
    instruction: str = Field(min_length=3, max_length=300)
    requires_confirmation: bool = True


class PredictiveReport(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    owner_name: str = "MASTER Brano"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    horizon_minutes: int
    scenarios: list[ScenarioForecast]
    opportunities: list[OpportunityScore]
    execution_plan: list[ExecutionStep]
    executive_recommendation: str
    requires_human_approval: bool = True
    automatic_execution: bool = False
    automatic_order_execution: bool = False


class WhatIfRequest(BaseModel):
    event: str = Field(min_length=3, max_length=300)
    affected_symbols: list[str] = Field(min_length=1, max_length=20)
    shock_strength: float = Field(default=0.5, ge=0, le=1)


class WhatIfImpact(BaseModel):
    symbol: str
    directional_bias: str
    volatility_impact: float = Field(ge=0, le=1)
    risk_impact: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)


class WhatIfReport(BaseModel):
    event: str
    impacts: list[WhatIfImpact]
    recommendation: str
    requires_human_approval: bool = True
    automatic_execution: bool = False


class PredictiveStatus(BaseModel):
    service: str = "predictive-intelligence"
    reports: int
    advisory_only: bool = True
    automatic_execution: bool = False
    automatic_order_execution: bool = False
