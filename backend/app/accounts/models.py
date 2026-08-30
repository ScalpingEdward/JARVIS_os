from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class AccountType(StrEnum):
    """The kind of account AURON manages. Prop accounts must respect a prop-firm
    rule set; live accounts trade real capital; demo accounts are for validation."""

    prop = "prop"
    live = "live"
    demo = "demo"


class AccountStatus(StrEnum):
    active = "active"
    suspended = "suspended"
    breached = "breached"
    passed = "passed"


class DrawdownType(StrEnum):
    static = "static"
    trailing = "trailing"


class PropFirmRules(BaseModel):
    """The hard rule set a prop-firm evaluation/funded account must respect.

    Defaults mirror common prop-firm challenges (e.g. 5% daily, 10% total,
    8% profit target). These are constraints AURON must never knowingly breach,
    not suggestions."""

    max_daily_loss_pct: float = Field(default=5.0, gt=0, le=100)
    max_total_drawdown_pct: float = Field(default=10.0, gt=0, le=100)
    profit_target_pct: float = Field(default=8.0, ge=0, le=100)
    min_trading_days: int = Field(default=0, ge=0, le=365)
    drawdown_type: DrawdownType = DrawdownType.static


class TradingAccountCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    account_type: AccountType
    broker: str = Field(min_length=1, max_length=120)
    login: str = Field(min_length=1, max_length=60)
    server: str = Field(min_length=1, max_length=120)
    currency: str = Field(default="USD", min_length=1, max_length=10)
    initial_balance: float = Field(gt=0)
    max_strategies: int = Field(default=2, ge=1, le=10)
    prop_rules: PropFirmRules | None = None

    @model_validator(mode="after")
    def validate_prop_rules(self):
        if self.account_type == AccountType.prop and self.prop_rules is None:
            raise ValueError("prop accounts require prop_rules")
        return self


class TradingAccountRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    label: str
    account_type: AccountType
    broker: str
    login: str
    server: str
    currency: str
    initial_balance: float
    max_strategies: int
    prop_rules: PropFirmRules | None
    status: AccountStatus = AccountStatus.active
    balance: float
    equity: float
    day_start_balance: float
    peak_equity: float
    trading_days: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StrategyAssignmentCreate(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=80)
    strategy_name: str = Field(min_length=1, max_length=120)
    allocation_pct: float = Field(gt=0, le=100)
    enabled: bool = True


class StrategyAssignment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    account_id: UUID
    strategy_id: str
    strategy_name: str
    allocation_pct: float
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AccountStateUpdate(BaseModel):
    """A broker snapshot of the account's live money state. ``day_start_balance``
    is optional: when omitted the stored value is kept, letting callers push
    intraday equity updates without resetting the daily baseline."""

    balance: float = Field(gt=0)
    equity: float = Field(gt=0)
    day_start_balance: float | None = Field(default=None, gt=0)
    as_of_date: str | None = Field(
        default=None,
        description="UTC date (YYYY-MM-DD) of the snapshot; defaults to today. Used to count distinct trading days.",
    )


class AccountComplianceStatus(BaseModel):
    account_id: UUID
    account_type: AccountType
    status: AccountStatus
    balance: float
    equity: float
    day_start_balance: float
    peak_equity: float
    daily_loss_pct: float
    total_drawdown_pct: float
    profit_pct: float
    trading_days: int
    daily_loss_headroom_pct: float | None = None
    drawdown_headroom_pct: float | None = None
    profit_target_progress_pct: float | None = None
    min_trading_days_met: bool | None = None
    breached: bool = False
    breach_reasons: list[str] = Field(default_factory=list)
