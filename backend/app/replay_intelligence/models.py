from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class TradeDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


class TradeOutcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


class JournalEntryCreate(BaseModel):
    replay_session_id: UUID
    symbol: str = Field(min_length=1, max_length=40)
    timeframe: str = Field(min_length=1, max_length=10)
    direction: TradeDirection
    entry_price: float = Field(gt=0)
    exit_price: float = Field(gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    risk_amount: float = Field(default=0, ge=0)
    fees: float = Field(default=0, ge=0)
    setup_tags: list[str] = Field(default_factory=list, max_length=20)
    mistakes: list[str] = Field(default_factory=list, max_length=20)
    notes: str = Field(default="", max_length=4000)
    human_approved: bool = True
    automatic_execution: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "JournalEntryCreate":
        if self.automatic_execution:
            raise ValueError("automatic execution is disabled")
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class JournalEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    replay_session_id: UUID
    symbol: str
    timeframe: str
    direction: TradeDirection
    entry_price: float
    exit_price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_amount: float
    fees: float
    pnl: float
    r_multiple: float | None = None
    outcome: TradeOutcome
    setup_tags: list[str]
    mistakes: list[str]
    notes: str
    human_approved: bool = True
    automatic_execution: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JournalSummary(BaseModel):
    total_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate_pct: float
    net_pnl: float
    gross_profit: float
    gross_loss: float
    profit_factor: float | None
    average_r: float | None
    best_setup_tags: list[str]
    recurring_mistakes: list[str]
    recommendation: str


class ReplayIntelligenceStatus(BaseModel):
    service: str = "replay-intelligence"
    version: str = "7.1"
    journal_enabled: bool = True
    analytics_enabled: bool = True
    simulation_only: bool = True
    automatic_execution: bool = False
    human_approval_required: bool = True
