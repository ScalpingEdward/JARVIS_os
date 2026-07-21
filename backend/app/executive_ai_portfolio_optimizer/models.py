from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PortfolioOptimizerState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    INPUT_INVALID = "input-invalid"
    OPTIMIZATION_PENDING = "optimization-pending"
    REVIEW_REQUIRED = "review-required"
    APPROVAL_REQUIRED = "approval-required"
    RECOMMENDATION_READY = "recommendation-ready"
    APPROVED = "approved"
    ARCHIVED = "archived"
    FAILED = "failed"


class StrategyPerformanceInput(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=120)
    strategy_type: str = Field(min_length=1, max_length=80)
    current_weight_pct: float = Field(ge=0, le=100)
    trades: int = Field(ge=0)
    win_rate_pct: float = Field(ge=0, le=100)
    expectancy_r: float
    profit_factor: float = Field(ge=0)
    sharpe: float
    sortino: float
    max_drawdown_pct: float = Field(ge=0, le=100)
    recovery_factor: float
    ulcer_index: float = Field(ge=0)
    volatility_pct: float = Field(ge=0)
    correlation_to_portfolio: float = Field(ge=-1, le=1)
    stability_score: float = Field(ge=0, le=100)
    shadow_validated_by_v19_09: bool = False
    journal_validated_by_v19_10: bool = False


class StressScenarioInput(BaseModel):
    flash_crash_loss_pct: float = Field(ge=0, le=100)
    spread_explosion_loss_pct: float = Field(ge=0, le=100)
    liquidity_removal_loss_pct: float = Field(ge=0, le=100)
    server_delay_loss_pct: float = Field(ge=0, le=100)
    slippage_loss_pct: float = Field(ge=0, le=100)


class PortfolioOptimizerCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    account_equity: float = Field(gt=0)
    daily_loss_limit_pct: float = Field(gt=0, le=100)
    max_drawdown_limit_pct: float = Field(gt=0, le=100)
    max_portfolio_heat_pct: float = Field(gt=0, le=100)
    max_strategy_weight_pct: float = Field(gt=0, le=100)
    cash_floor_pct: float = Field(ge=0, le=100)
    monte_carlo_runs: int = Field(default=1000, ge=100, le=10000)
    upstream_risk_brain_blocked: bool = False
    account_risk_approved: bool = False
    prop_rules_approved: bool = False
    market_allowed_by_v19_08: bool = False
    human_approved: bool = False
    strategies: list[StrategyPerformanceInput] = Field(min_length=1, max_length=30)
    stress: StressScenarioInput

    @model_validator(mode="after")
    def validate_weights(self):
        if sum(item.current_weight_pct for item in self.strategies) > 100.0001:
            raise ValueError("strategy weights cannot exceed 100 percent")
        if self.cash_floor_pct + sum(item.current_weight_pct for item in self.strategies) > 100.0001:
            raise ValueError("cash floor plus strategy weights cannot exceed 100 percent")
        return self


class PortfolioOptimizerExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern="^(approve|archive)$")
    human_approved: bool | None = None


class StrategyRecommendation(BaseModel):
    strategy_id: str
    score: float
    current_weight_pct: float
    recommended_weight_pct: float
    action: str
    rationale: str


class MonteCarloSummary(BaseModel):
    runs: int
    worst_case_return_pct: float
    median_return_pct: float
    best_case_return_pct: float
    risk_of_ruin_pct: float
    estimated_recovery_days: int


class StressTestSummary(BaseModel):
    worst_scenario_loss_pct: float
    portfolio_heat_pct: float
    passed: bool


class PortfolioOptimizerRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: PortfolioOptimizerState
    detail: str
    request: PortfolioOptimizerCreate
    portfolio_score: float = 0
    recommended_cash_pct: float = 0
    recommendations: list[StrategyRecommendation] = Field(default_factory=list)
    monte_carlo: MonteCarloSummary | None = None
    stress_test: StressTestSummary | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PortfolioOptimizerStatus(BaseModel):
    module: str = "executive-ai-portfolio-optimizer"
    version: str = "19.11"
    workspace_id: str
    total_records: int
    ready_records: int
    blocked_records: int


class PortfolioOptimizerAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: PortfolioOptimizerState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
