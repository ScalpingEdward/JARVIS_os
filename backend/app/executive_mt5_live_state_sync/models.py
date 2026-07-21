from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class LiveSyncState(str, Enum):
    BLOCKED = "blocked"
    EXECUTOR_REQUIRED = "executor-required"
    SYNC_PENDING = "sync-pending"
    ACCOUNT_MISMATCH = "account-mismatch"
    ORDER_MISMATCH = "order-mismatch"
    POSITION_MISMATCH = "position-mismatch"
    DEAL_MISMATCH = "deal-mismatch"
    HISTORY_REQUIRED = "history-required"
    PARTIAL_CLOSE_DETECTED = "partial-close-detected"
    MANUAL_TRADE_DETECTED = "manual-trade-detected"
    DRIFT_DETECTED = "drift-detected"
    RESYNC_REQUIRED = "resync-required"
    SYNCHRONIZED = "synchronized"
    RECONCILIATION_COMPLETE = "reconciliation-complete"
    FAILED = "failed"


class ExpectedTicket(BaseModel):
    broker_ticket: int = Field(gt=0)
    symbol: str = Field(min_length=1, max_length=32)
    volume: float = Field(ge=0)


class LiveSyncCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    executor_reconciliation_required: bool = False
    account_login: int = Field(gt=0)
    approved_account_logins: list[int] = Field(default_factory=list)
    expected_positions: list[ExpectedTicket] = Field(default_factory=list)
    expected_orders: list[ExpectedTicket] = Field(default_factory=list)
    expected_deal_tickets: list[int] = Field(default_factory=list)
    history_from_epoch: int = Field(default=0, ge=0)
    account_risk_approved: bool = False
    prop_rules_approved: bool = False
    risk_brain_blocked: bool = False
    human_recovery_approved: bool = False


class LiveSyncExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = "synchronize"
    human_recovery_approved: bool | None = None


class AccountSnapshot(BaseModel):
    login: int
    balance: float
    equity: float
    margin: float
    margin_free: float
    margin_level: float
    floating_profit: float
    daily_profit: float


class LiveSyncRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: LiveSyncState
    detail: str
    request: LiveSyncCreate
    account: AccountSnapshot | None = None
    position_tickets: list[int] = Field(default_factory=list)
    order_tickets: list[int] = Field(default_factory=list)
    deal_tickets: list[int] = Field(default_factory=list)
    manual_trade_tickets: list[int] = Field(default_factory=list)
    missing_position_tickets: list[int] = Field(default_factory=list)
    missing_order_tickets: list[int] = Field(default_factory=list)
    partial_close_tickets: list[int] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LiveSyncStatus(BaseModel):
    module: str = "executive-mt5-live-state-sync"
    version: str = "19.02"
    workspace_id: str
    total_records: int
    synchronized_records: int
    drift_records: int


class LiveSyncAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: LiveSyncState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
