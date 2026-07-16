from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class StrategyStatus(str, Enum):
    draft = "draft"
    validated = "validated"
    invalid = "invalid"
    archived = "archived"


class RuleKind(str, Enum):
    entry = "entry"
    filter = "filter"
    exit = "exit"
    risk = "risk"


class LogicalOperator(str, Enum):
    all = "all"
    any = "any"


class StrategyRule(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    kind: RuleKind
    name: str = Field(min_length=2, max_length=120)
    expression: str = Field(min_length=3, max_length=500)
    timeframe: str | None = Field(default=None, max_length=20)
    enabled: bool = True


class RiskConfig(BaseModel):
    risk_per_trade_pct: float = Field(default=1.0, gt=0, le=5)
    max_daily_risk_pct: float = Field(default=3.0, gt=0, le=10)
    max_open_positions: int = Field(default=3, ge=1, le=50)
    minimum_rr: float = Field(default=2.0, ge=0.5, le=20)
    stop_loss_required: bool = True
    automatic_execution: bool = False


class StrategyCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=5, max_length=1000)
    symbols: list[str] = Field(min_length=1, max_length=30)
    entry_logic: LogicalOperator = LogicalOperator.all
    exit_logic: LogicalOperator = LogicalOperator.any
    rules: list[StrategyRule] = Field(min_length=2, max_length=100)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    owner_name: str = "MASTER Brano"

    @model_validator(mode="after")
    def require_entry_and_exit_rules(self) -> "StrategyCreate":
        kinds = {rule.kind for rule in self.rules if rule.enabled}
        if RuleKind.entry not in kinds:
            raise ValueError("At least one enabled entry rule is required")
        if RuleKind.exit not in kinds:
            raise ValueError("At least one enabled exit rule is required")
        if self.risk.automatic_execution:
            raise ValueError("Automatic execution is not permitted")
        return self


class ValidationIssue(BaseModel):
    severity: str
    code: str
    message: str


class StrategyRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    version: int = 1
    status: StrategyStatus = StrategyStatus.draft
    name: str
    description: str
    symbols: list[str]
    entry_logic: LogicalOperator
    exit_logic: LogicalOperator
    rules: list[StrategyRule]
    risk: RiskConfig
    owner_name: str = "MASTER Brano"
    issues: list[ValidationIssue] = Field(default_factory=list)
    backtest_ready: bool = False
    requires_human_approval: bool = True
    automatic_execution: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StrategyStatusResponse(BaseModel):
    owner_name: str = "MASTER Brano"
    strategies: int
    validated: int
    backtest_ready: int
    automatic_execution: bool = False
    automatic_order_execution: bool = False


class StrategyListResponse(BaseModel):
    items: list[StrategyRecord]
    count: int
