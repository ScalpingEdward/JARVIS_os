from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PendingOrderState(str, Enum):
    BLOCKED = "blocked"
    PROFIT_LOCK_REQUIRED = "profit-lock-required"
    REQUEST_INVALID = "request-invalid"
    PRICE_INVALID = "price-invalid"
    EXPIRATION_INVALID = "expiration-invalid"
    OCO_INVALID = "oco-invalid"
    RISK_REJECTED = "risk-rejected"
    APPROVAL_REQUIRED = "approval-required"
    PLACEMENT_PENDING = "placement-pending"
    BROKER_ACK_PENDING = "broker-ack-pending"
    OCO_ARMED = "oco-armed"
    CANCEL_PENDING = "cancel-pending"
    RECONCILIATION_REQUIRED = "reconciliation-required"
    PENDING_READY = "pending-ready"
    FAILED = "failed"


class PendingOrderAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    profit_lock_ready: bool = False
    symbol: str = Field(min_length=1, max_length=32)
    order_type: str
    volume: float = Field(gt=0)
    entry_price: float = Field(gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    current_bid: float = Field(gt=0)
    current_ask: float = Field(gt=0)
    point: float = Field(gt=0)
    stop_level_points: int = Field(ge=0)
    freeze_level_points: int = Field(ge=0)
    expiration_at: datetime | None = None
    oco_group_id: str | None = Field(default=None, max_length=120)
    peer_order_defined: bool = False
    account_risk_approved: bool = False
    prop_rules_approved: bool = False
    risk_brain_blocked: bool = False
    human_approved: bool = False
    placement_dispatched: bool = False
    broker_acknowledged: bool = False
    broker_order_id: str | None = Field(default=None, max_length=120)
    broker_retcode: int | None = None
    peer_cancel_required: bool = False
    peer_cancel_acknowledged: bool = False
    pending_orders_reconciled: bool = False
    account_snapshot_reconciled: bool = False
    terminal_error: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_prices(self):
        if self.current_ask < self.current_bid:
            raise ValueError("current_ask must be greater than or equal to current_bid")
        return self


class PendingOrderAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    state: PendingOrderState
    reasons: list[str] = Field(default_factory=list)
    payload: PendingOrderAssessmentCreate


class PendingOrderExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    human_approved: bool = True
    placement_dispatched: bool = True
    broker_acknowledged: bool = True
    broker_order_id: str | None = None
    broker_retcode: int | None = None
    peer_cancel_acknowledged: bool = False
    pending_orders_reconciled: bool = False
    account_snapshot_reconciled: bool = False
    terminal_error: str | None = None


class PendingOrderStatus(BaseModel):
    workspace_id: str
    latest_state: PendingOrderState | None
    count: int


class AuditRecord(BaseModel):
    workspace_id: str
    action: str
    actor_id: str
    record_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
