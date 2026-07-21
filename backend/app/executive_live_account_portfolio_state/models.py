from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class AccountPortfolioState(str, Enum):
    BLOCKED = "blocked"
    SYNCHRONIZATION_REQUIRED = "synchronization-required"
    PORTFOLIO_BUILDING = "portfolio-building"
    ACCOUNT_UNHEALTHY = "account-unhealthy"
    MARGIN_WARNING = "margin-warning"
    MARGIN_CRITICAL = "margin-critical"
    DRAWDOWN_WARNING = "drawdown-warning"
    DRAWDOWN_CRITICAL = "drawdown-critical"
    PROP_LIMIT_WARNING = "prop-limit-warning"
    PROP_LIMIT_BREACHED = "prop-limit-breached"
    RECOVERY_REQUIRED = "recovery-required"
    PORTFOLIO_READY = "portfolio-ready"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


class AccountPortfolioSnapshotCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    reconciliation_complete: bool = False
    account_login: int = Field(gt=0)
    balance: float = Field(ge=0)
    equity: float = Field(ge=0)
    margin: float = Field(ge=0)
    free_margin: float = Field(ge=0)
    margin_level: float = Field(ge=0)
    floating_pl: float = 0
    daily_pl: float = 0
    weekly_pl: float = 0
    monthly_pl: float = 0
    equity_high_watermark: float = Field(ge=0)
    daily_start_equity: float = Field(ge=0)
    open_positions: int = Field(default=0, ge=0)
    pending_orders: int = Field(default=0, ge=0)
    gross_exposure: float = Field(default=0, ge=0)
    risk_budget_used: float = Field(default=0, ge=0)
    risk_budget_limit: float = Field(default=0, ge=0)
    daily_loss_limit: float = Field(default=0, ge=0)
    max_loss_limit: float = Field(default=0, ge=0)
    margin_warning_level: float = Field(default=250, gt=0)
    margin_critical_level: float = Field(default=150, gt=0)
    drawdown_warning_pct: float = Field(default=3, ge=0)
    drawdown_critical_pct: float = Field(default=5, ge=0)
    prop_warning_ratio: float = Field(default=0.8, gt=0, le=1)
    account_risk_approved: bool = False
    prop_rules_approved: bool = False
    risk_brain_blocked: bool = False

    @model_validator(mode="after")
    def validate_thresholds(self):
        if self.margin_critical_level >= self.margin_warning_level:
            raise ValueError("margin critical level must be below warning level")
        if self.drawdown_critical_pct < self.drawdown_warning_pct:
            raise ValueError("drawdown critical percentage must be >= warning percentage")
        return self


class AccountPortfolioRefreshRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    human_approved: bool = False
    action: str = "refresh"


class AccountPortfolioSnapshot(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: AccountPortfolioState
    detail: str
    request: AccountPortfolioSnapshotCreate
    current_drawdown_pct: float = 0
    daily_drawdown_pct: float = 0
    portfolio_heat_pct: float = 0
    buying_power: float = 0
    account_health_score: float = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AccountPortfolioStatus(BaseModel):
    module: str = "executive-live-account-portfolio-state"
    version: str = "19.03"
    workspace_id: str
    total_records: int
    healthy_records: int
    critical_records: int


class AccountPortfolioAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: AccountPortfolioState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
