from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PortfolioDecision(str, Enum):
    INCLUDED = "included"
    REDUCED_WEIGHT = "reduced_weight"
    SHADOW_ONLY = "shadow_only"
    EXCLUDED = "excluded"


class PortfolioHealth(str, Enum):
    STRONG = "strong"
    ACCEPTABLE = "acceptable"
    FRAGILE = "fragile"
    BLOCKED = "blocked"


class StrategyCandidate(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=50)
    symbol: str = Field(min_length=1, max_length=30)
    market_regime: str = Field(min_length=1, max_length=80)
    asset_cluster: str = Field(min_length=1, max_length=80)
    direction_cluster: str = Field(min_length=1, max_length=80)
    adaptive_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    proposed_weight: float = Field(ge=0, le=1)
    expected_drawdown_pct: float = Field(ge=0, le=100)
    risk_contribution_pct: float = Field(ge=0, le=100)
    eligible: bool = True
    shadow_only: bool = False


class CorrelationLink(BaseModel):
    strategy_a: str = Field(min_length=1, max_length=100)
    strategy_b: str = Field(min_length=1, max_length=100)
    correlation: float = Field(ge=-1, le=1)

    @model_validator(mode="after")
    def validate_pair(self):
        if self.strategy_a == self.strategy_b:
            raise ValueError("Correlation link requires two distinct strategies")
        return self


class PortfolioPolicy(BaseModel):
    max_strategy_weight: float = Field(default=0.35, gt=0, le=1)
    max_symbol_weight: float = Field(default=0.50, gt=0, le=1)
    max_cluster_weight: float = Field(default=0.60, gt=0, le=1)
    max_total_risk_pct: float = Field(default=6.0, gt=0, le=100)
    max_expected_drawdown_pct: float = Field(default=10.0, gt=0, le=100)
    high_correlation_threshold: float = Field(default=0.75, ge=0, le=1)
    minimum_adaptive_score: float = Field(default=60.0, ge=0, le=100)
    minimum_confidence: float = Field(default=0.55, ge=0, le=1)


class PortfolioRunCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    account_profile_id: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    candidates: list[StrategyCandidate] = Field(min_length=1)
    correlations: list[CorrelationLink] = Field(default_factory=list)
    policy: PortfolioPolicy = Field(default_factory=PortfolioPolicy)

    @model_validator(mode="after")
    def validate_unique_candidates(self):
        ids = [item.strategy_id for item in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("Strategy candidates must be unique")
        known = set(ids)
        for link in self.correlations:
            if link.strategy_a not in known or link.strategy_b not in known:
                raise ValueError("Correlation links must reference submitted strategies")
        return self


class StrategyPortfolioResult(BaseModel):
    strategy_id: str
    strategy_version: str
    symbol: str
    asset_cluster: str
    decision: PortfolioDecision
    recommended_weight: float = Field(ge=0, le=1)
    portfolio_rank: int = Field(ge=1)
    score: float = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)


class PortfolioMetrics(BaseModel):
    portfolio_score: float = Field(ge=0, le=100)
    diversification_score: float = Field(ge=0, le=100)
    concentration_score: float = Field(ge=0, le=100)
    correlation_risk_score: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=100)
    stability_score: float = Field(ge=0, le=100)
    total_recommended_weight: float = Field(ge=0, le=1)
    total_risk_contribution_pct: float = Field(ge=0)
    weighted_expected_drawdown_pct: float = Field(ge=0)


class PortfolioRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    account_profile_id: str
    actor_id: str
    health: PortfolioHealth
    metrics: PortfolioMetrics
    results: list[StrategyPortfolioResult]
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PortfolioRunList(BaseModel):
    items: list[PortfolioRun]
    count: int


class PortfolioStatus(BaseModel):
    module: str = "executive-portfolio-intelligence"
    version: str = "18.34"
    autonomous_execution: bool = False
    capabilities: list[str]


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    entity_id: str
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
