from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class TradeJournalState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    INPUT_INVALID = "input-invalid"
    JOURNAL_PENDING = "journal-pending"
    JOURNAL_COMPLETE = "journal-complete"
    REPLAY_READY = "replay-ready"
    REVIEW_REQUIRED = "review-required"
    LESSON_APPROVED = "lesson-approved"
    ARCHIVED = "archived"
    FAILED = "failed"


class TradeDecisionEvidence(BaseModel):
    trade_id: str = Field(min_length=1, max_length=120)
    strategy_id: str = Field(min_length=1, max_length=120)
    account_id: str = Field(min_length=1, max_length=120)
    symbol: str = Field(min_length=1, max_length=40)
    side: str = Field(pattern="^(buy|sell)$")
    setup_name: str = Field(min_length=1, max_length=160)
    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    exit_price: float = Field(gt=0)
    risk_amount: float = Field(gt=0)
    pnl: float
    planned_rr: float = Field(gt=0)
    realized_rr: float
    signal_confidence: float = Field(ge=0, le=100)
    market_score: float = Field(ge=0, le=100)
    market_regime: str = Field(min_length=1, max_length=80)
    session: str = Field(min_length=1, max_length=80)
    entry_reason: str = Field(min_length=1, max_length=1000)
    exit_reason: str = Field(min_length=1, max_length=1000)
    mae_r: float = Field(ge=0)
    mfe_r: float = Field(ge=0)
    slippage_bps: float = Field(ge=0)
    holding_seconds: int = Field(ge=0)
    routed_by_v19_06: bool = False
    market_allowed_by_v19_08: bool = False
    shadow_validated_by_v19_09: bool = False
    opened_at: datetime
    closed_at: datetime

    @model_validator(mode="after")
    def validate_trade(self):
        if self.closed_at < self.opened_at:
            raise ValueError("closed_at must be after opened_at")
        if self.side == "buy" and not self.stop_loss < self.entry_price < self.take_profit:
            raise ValueError("buy trade levels are invalid")
        if self.side == "sell" and not self.take_profit < self.entry_price < self.stop_loss:
            raise ValueError("sell trade levels are invalid")
        return self


class InstitutionalTradeJournalCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    upstream_risk_brain_blocked: bool = False
    account_risk_approved: bool = False
    prop_rules_approved: bool = False
    human_approved: bool = False
    trade: TradeDecisionEvidence
    notes: list[str] = Field(default_factory=list, max_length=30)
    tags: list[str] = Field(default_factory=list, max_length=30)


class TradeJournalExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern="^(complete|approve-lesson|archive)$")
    human_approved: bool | None = None


class ReplayCheckpoint(BaseModel):
    name: str
    expected_action: str
    evidence: str
    passed: bool


class InstitutionalTradeJournalRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: TradeJournalState
    detail: str
    request: InstitutionalTradeJournalCreate
    setup_quality_score: float = 0
    execution_quality_score: float = 0
    management_quality_score: float = 0
    discipline_score: float = 0
    process_score: float = 0
    outcome_classification: str = "unclassified"
    lesson: str = ""
    replay: list[ReplayCheckpoint] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InstitutionalTradeJournalStatus(BaseModel):
    module: str = "executive-institutional-trade-journal"
    version: str = "19.10"
    workspace_id: str
    total_records: int
    complete_records: int
    review_records: int


class InstitutionalTradeJournalAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: TradeJournalState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
