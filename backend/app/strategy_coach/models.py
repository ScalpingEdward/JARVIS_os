from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class CoachPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PlaybookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    symbol: str = Field(min_length=1, max_length=40)
    timeframe: str = Field(min_length=1, max_length=10)
    minimum_trades: int = Field(default=10, ge=5, le=1000)
    win_rate_pct: float = Field(ge=0, le=100)
    average_r: float | None = None
    profit_factor: float | None = Field(default=None, ge=0)
    best_setups: list[str] = Field(default_factory=list, max_length=20)
    recurring_mistakes: list[str] = Field(default_factory=list, max_length=20)
    trading_rules: list[str] = Field(default_factory=list, max_length=30)
    human_approved: bool = True
    automatic_execution: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "PlaybookCreate":
        if self.automatic_execution:
            raise ValueError("automatic execution is disabled")
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class CoachAction(BaseModel):
    priority: CoachPriority
    category: str
    instruction: str


class StrategyPlaybook(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    symbol: str
    timeframe: str
    readiness_score: int = Field(ge=0, le=100)
    approved_setups: list[str]
    blocked_mistakes: list[str]
    pre_trade_checklist: list[str]
    improvement_actions: list[CoachAction]
    live_use_recommended: bool = False
    human_approved: bool = True
    automatic_execution: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StrategyCoachStatus(BaseModel):
    service: str = "strategy-coach"
    version: str = "7.2"
    adaptive_playbooks: bool = True
    advisory_only: bool = True
    automatic_execution: bool = False
    human_approval_required: bool = True
