from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ValidationState(str, Enum):
    READY = "ready"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"


class TradingDay(BaseModel):
    day: int = Field(ge=1, le=10000)
    starting_balance: float = Field(gt=0)
    ending_balance: float = Field(gt=0)
    lowest_equity: float = Field(gt=0)
    trades: int = Field(default=0, ge=0, le=10000)

    @model_validator(mode="after")
    def validate_equity(self) -> "TradingDay":
        if self.lowest_equity > max(self.starting_balance, self.ending_balance):
            raise ValueError("lowest equity cannot exceed both balance values")
        return self


class ValidationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    account_size: float = Field(gt=0)
    profit_target_pct: float = Field(default=10, gt=0, le=100)
    max_daily_drawdown_pct: float = Field(default=5, gt=0, le=100)
    max_total_drawdown_pct: float = Field(default=10, gt=0, le=100)
    minimum_trading_days: int = Field(default=4, ge=1, le=365)
    maximum_single_day_profit_share_pct: float | None = Field(default=None, gt=0, le=100)
    days: list[TradingDay] = Field(min_length=1, max_length=10000)
    human_approved: bool = True
    automatic_execution: bool = False

    @model_validator(mode="after")
    def enforce_safety_and_order(self) -> "ValidationCreate":
        if self.automatic_execution:
            raise ValueError("automatic execution is disabled")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if any(a.day >= b.day for a, b in zip(self.days, self.days[1:])):
            raise ValueError("trading days must be strictly chronological")
        return self


class RuleResult(BaseModel):
    rule: str
    passed: bool
    actual: float | int | None = None
    limit: float | int | None = None
    message: str


class ValidationReport(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    account_size: float
    state: ValidationState
    current_balance: float
    net_profit: float
    profit_pct: float
    completed_trading_days: int
    total_trades: int
    maximum_daily_drawdown_pct: float
    maximum_total_drawdown_pct: float
    largest_day_profit_share_pct: float | None
    rules: list[RuleResult]
    blockers: list[str]
    recommendation: str
    simulation_only: bool = True
    automatic_execution: bool = False
    human_approval_required: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ForwardValidationStatus(BaseModel):
    service: str = "forward-validation"
    version: str = "7.3"
    prop_readiness_enabled: bool = True
    simulation_only: bool = True
    automatic_execution: bool = False
    human_approval_required: bool = True
