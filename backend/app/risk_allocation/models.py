from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class AccountState(str, Enum):
    ACTIVE = "active"
    CAUTION = "caution"
    BLOCKED = "blocked"


class AccountInput(BaseModel):
    account_id: str = Field(min_length=1, max_length=80)
    provider: str = Field(min_length=1, max_length=80)
    balance: float = Field(gt=0)
    daily_drawdown_remaining: float = Field(ge=0)
    total_drawdown_remaining: float = Field(ge=0)
    requested_risk_pct: float = Field(default=1.0, ge=0, le=10)
    correlation_group: str = Field(default="default", min_length=1, max_length=80)
    enabled: bool = True


class AllocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    portfolio_risk_budget_pct: float = Field(default=2.0, gt=0, le=20)
    max_account_risk_pct: float = Field(default=1.0, gt=0, le=10)
    max_correlation_group_risk_pct: float = Field(default=1.5, gt=0, le=20)
    safety_buffer_pct: float = Field(default=20, ge=0, le=90)
    accounts: list[AccountInput] = Field(min_length=1, max_length=100)
    human_approved: bool = True
    automatic_execution: bool = False

    @model_validator(mode="after")
    def enforce_safety_and_uniqueness(self) -> "AllocationCreate":
        if self.automatic_execution:
            raise ValueError("automatic execution is disabled")
        if not self.human_approved:
            raise ValueError("human approval is required")
        ids = [item.account_id for item in self.accounts]
        if len(ids) != len(set(ids)):
            raise ValueError("account ids must be unique")
        return self


class AccountAllocation(BaseModel):
    account_id: str
    provider: str
    correlation_group: str
    state: AccountState
    requested_risk_amount: float
    allocated_risk_amount: float
    allocated_risk_pct: float
    capacity_amount: float
    blockers: list[str]


class AllocationPlan(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    total_balance: float
    portfolio_risk_budget_amount: float
    allocated_risk_amount: float
    unused_risk_amount: float
    allocations: list[AccountAllocation]
    correlation_group_allocations: dict[str, float]
    blockers: list[str]
    recommendation: str
    advisory_only: bool = True
    automatic_execution: bool = False
    human_approval_required: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskAllocationStatus(BaseModel):
    service: str = "risk-allocation"
    version: str = "7.4"
    multi_account_enabled: bool = True
    correlation_limits_enabled: bool = True
    advisory_only: bool = True
    automatic_execution: bool = False
    human_approval_required: bool = True
