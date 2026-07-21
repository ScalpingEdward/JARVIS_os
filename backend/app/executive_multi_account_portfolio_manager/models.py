from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class MultiAccountPortfolioState(str, Enum):
    BLOCKED = "blocked"
    PORTFOLIO_STATE_REQUIRED = "portfolio-state-required"
    ALLOCATION_PENDING = "allocation-pending"
    ALLOCATION_APPROVED = "allocation-approved"
    ACCOUNT_EXCLUDED = "account-excluded"
    ACCOUNT_DEGRADED = "account-degraded"
    PORTFOLIO_UNBALANCED = "portfolio-unbalanced"
    REBALANCING_REQUIRED = "rebalancing-required"
    CAPACITY_EXHAUSTED = "capacity-exhausted"
    CAPITAL_CONSTRAINED = "capital-constrained"
    MONITORING = "monitoring"
    HEALTHY = "healthy"
    FAILED = "failed"


class AccountAllocationInput(BaseModel):
    account_id: str = Field(min_length=1, max_length=100)
    broker: str = Field(min_length=1, max_length=100)
    prop_firm: str | None = Field(default=None, max_length=100)
    balance: float = Field(ge=0)
    equity: float = Field(ge=0)
    current_risk: float = Field(default=0, ge=0)
    max_risk: float = Field(gt=0)
    daily_drawdown_pct: float = Field(default=0, ge=0)
    max_drawdown_pct: float = Field(default=0, ge=0)
    health_score: float = Field(default=100, ge=0, le=100)
    correlation_score: float = Field(default=0, ge=0, le=1)
    enabled: bool = True
    prop_rules_approved: bool = False
    account_risk_approved: bool = False


class MultiAccountAllocationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    portfolio_risk_approved: bool = False
    upstream_risk_brain_blocked: bool = False
    requested_total_risk: float = Field(gt=0)
    max_portfolio_risk: float = Field(gt=0)
    max_portfolio_heat_pct: float = Field(default=80, gt=0)
    rebalance_threshold_pct: float = Field(default=20, ge=0)
    human_approved: bool = False
    accounts: list[AccountAllocationInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_accounts(self):
        ids = [account.account_id for account in self.accounts]
        if len(ids) != len(set(ids)):
            raise ValueError("account_id values must be unique")
        return self


class MultiAccountAllocationExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = "activate"
    human_approved: bool | None = None


class AccountAllocationResult(BaseModel):
    account_id: str
    allocated_risk: float = 0
    weight_pct: float = 0
    capacity_remaining: float = 0
    capital_allocation_score: float = 0
    excluded: bool = False
    exclusion_reason: str | None = None


class MultiAccountAllocationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: MultiAccountPortfolioState
    detail: str
    request: MultiAccountAllocationCreate
    total_balance: float = 0
    total_equity: float = 0
    total_current_risk: float = 0
    allocated_total_risk: float = 0
    portfolio_heat_pct: float = 0
    portfolio_health_score: float = 0
    allocations: list[AccountAllocationResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MultiAccountPortfolioStatus(BaseModel):
    module: str = "executive-multi-account-portfolio-manager"
    version: str = "19.05"
    workspace_id: str
    total_records: int
    healthy_records: int
    blocked_records: int


class MultiAccountPortfolioAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: MultiAccountPortfolioState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
