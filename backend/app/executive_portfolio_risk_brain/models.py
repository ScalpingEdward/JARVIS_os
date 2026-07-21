from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PortfolioRiskState(str, Enum):
    BLOCKED = "blocked"
    ACCOUNT_STATE_REQUIRED = "account-state-required"
    INPUT_INVALID = "input-invalid"
    RISK_BUDGET_EXHAUSTED = "risk-budget-exhausted"
    PORTFOLIO_HEAT_HIGH = "portfolio-heat-high"
    DRAWDOWN_GUARD = "drawdown-guard"
    DAILY_LOSS_GUARD = "daily-loss-guard"
    MARGIN_GUARD = "margin-guard"
    CONCENTRATION_GUARD = "concentration-guard"
    CORRELATION_GUARD = "correlation-guard"
    REDUCE_ONLY = "reduce-only"
    HALT_REQUIRED = "halt-required"
    APPROVAL_REQUIRED = "approval-required"
    RISK_APPROVED = "risk-approved"
    MONITORING = "monitoring"
    FAILED = "failed"


class PortfolioRiskAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    account_state_healthy: bool = False
    account_state_version: str = "19.03"
    equity: float = Field(gt=0)
    balance: float = Field(gt=0)
    free_margin: float = Field(ge=0)
    margin_level: float = Field(ge=0)
    current_drawdown_pct: float = Field(ge=0)
    daily_drawdown_pct: float = Field(ge=0)
    portfolio_heat_pct: float = Field(ge=0)
    risk_budget_used: float = Field(ge=0)
    risk_budget_limit: float = Field(gt=0)
    proposed_risk_amount: float = Field(ge=0)
    gross_exposure: float = Field(ge=0)
    largest_symbol_exposure_pct: float = Field(default=0, ge=0)
    max_symbol_exposure_pct: float = Field(default=35, gt=0, le=100)
    correlated_exposure_pct: float = Field(default=0, ge=0)
    max_correlated_exposure_pct: float = Field(default=60, gt=0, le=100)
    drawdown_guard_pct: float = Field(default=6, gt=0)
    daily_loss_guard_pct: float = Field(default=3, gt=0)
    min_margin_level: float = Field(default=150, gt=0)
    max_portfolio_heat_pct: float = Field(default=80, gt=0)
    hard_halt_drawdown_pct: float = Field(default=9, gt=0)
    account_risk_approved: bool = False
    prop_rules_approved: bool = False
    human_approved: bool = False
    risk_brain_blocked: bool = False

    @model_validator(mode="after")
    def validate_thresholds(self):
        if self.hard_halt_drawdown_pct < self.drawdown_guard_pct:
            raise ValueError("hard_halt_drawdown_pct must be >= drawdown_guard_pct")
        return self


class PortfolioRiskExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = "activate"
    human_approved: bool | None = None


class PortfolioRiskAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: PortfolioRiskState
    detail: str
    request: PortfolioRiskAssessmentCreate
    remaining_risk_budget: float = 0
    projected_portfolio_heat_pct: float = 0
    max_new_risk_amount: float = 0
    reduce_only: bool = False
    trading_halted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PortfolioRiskStatus(BaseModel):
    module: str = "executive-portfolio-risk-brain"
    version: str = "19.04"
    workspace_id: str
    total_records: int
    approved_records: int
    blocked_records: int
    halted_records: int


class PortfolioRiskAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: PortfolioRiskState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
