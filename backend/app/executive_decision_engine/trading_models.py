from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class TradingDecision(str, Enum):
    approve = "approve"
    reduce = "reduce"
    delay = "delay"
    shadow = "shadow"
    freeze = "freeze"
    reject = "reject"


class RiskState(str, Enum):
    normal = "normal"
    reduced = "reduced"
    frozen = "frozen"
    blocked = "blocked"


class PortfolioState(str, Enum):
    strong = "strong"
    acceptable = "acceptable"
    fragile = "fragile"
    blocked = "blocked"


class StrategyDecisionInput(BaseModel):
    strategy_key: str = Field(min_length=1, max_length=120)
    adaptive_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=100)
    portfolio_weight: float = Field(ge=0, le=100)
    risk_weight_multiplier: float = Field(ge=0, le=1)
    eligible: bool = True
    shadow_only: bool = False
    blocked: bool = False


class TradingDecisionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    owner_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    account_profile: str = Field(min_length=1, max_length=120)
    symbol: str = Field(min_length=1, max_length=40)
    timeframe: str = Field(min_length=1, max_length=20)
    regime_confidence: float = Field(ge=0, le=100)
    evidence_score: float = Field(ge=0, le=100)
    portfolio_score: float = Field(ge=0, le=100)
    portfolio_state: PortfolioState
    global_risk_score: float = Field(ge=0, le=100)
    risk_state: RiskState
    news_risk: float = Field(ge=0, le=100)
    strategies: list[StrategyDecisionInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_strategies(self):
        keys = [item.strategy_key for item in self.strategies]
        if len(keys) != len(set(keys)):
            raise ValueError("Strategy keys must be unique")
        return self


class TradingDecisionTrace(BaseModel):
    source: str
    outcome: str
    score: float | None = None
    reason: str


class TradingDecisionRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    source_key: str
    account_profile: str
    symbol: str
    timeframe: str
    decision: TradingDecision
    selected_strategy_key: str | None
    recommended_weight: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=100)
    quality_score: float = Field(ge=0, le=100)
    stability_score: float = Field(ge=0, le=100)
    explainability_score: float = Field(ge=0, le=100)
    consistency_score: float = Field(ge=0, le=100)
    risk_state: RiskState
    portfolio_state: PortfolioState
    reasons: list[str]
    trace: list[TradingDecisionTrace]
    decision_hash: str
    version: int = 1
    approval_required: bool = True
    autonomous_actions_enabled: bool = False
    created_at: datetime


class TradingDecisionStatusResponse(BaseModel):
    version: str = "18.36"
    decisions: int
    approved_recommendations: int
    restrictive_decisions: int
    autonomous_actions_enabled: bool = False


class TradingDecisionListResponse(BaseModel):
    items: list[TradingDecisionRecord]
    count: int
