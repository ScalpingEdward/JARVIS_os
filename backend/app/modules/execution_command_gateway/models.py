from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BrokerKind(str, Enum):
    MT5 = "mt5"
    DXTRADE = "dxtrade"
    CTRADER = "ctrader"
    FIX = "fix"
    REST = "rest"


class CommandType(str, Enum):
    PLACE_ORDER = "place-order"
    MODIFY_ORDER = "modify-order"
    CANCEL_ORDER = "cancel-order"
    CLOSE_POSITION = "close-position"
    PARTIAL_CLOSE = "partial-close"


class CommandState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    VALIDATION_FAILED = "validation-failed"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    QUEUED = "queued"
    DISPATCHED = "dispatched"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class GatewayCommand(str, Enum):
    APPROVE = "approve"
    QUEUE = "queue"
    DISPATCH = "dispatch"
    ACKNOWLEDGE = "acknowledge"
    FAIL = "fail"
    CANCEL = "cancel"
    ARCHIVE = "archive"


class ExecutionCommandCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=120)
    source_key: str = Field(..., min_length=1, max_length=240)
    workflow_record_id: str = Field(..., min_length=1, max_length=120)
    policy_record_id: str = Field(..., min_length=1, max_length=120)
    broker: BrokerKind
    account_id: str = Field(..., min_length=1, max_length=120)
    command_type: CommandType
    symbol: str = Field(..., min_length=2, max_length=32)
    side: str = Field(..., pattern="^(buy|sell)$")
    volume: float = Field(..., gt=0, le=1000)
    order_type: str = Field(default="market", pattern="^(market|limit|stop|stop-limit)$")
    price: Optional[float] = Field(default=None, gt=0)
    stop_loss: Optional[float] = Field(default=None, gt=0)
    take_profit: Optional[float] = Field(default=None, gt=0)
    position_id: Optional[str] = Field(default=None, max_length=120)
    client_order_id: Optional[str] = Field(default=None, max_length=120)
    idempotency_key: str = Field(..., min_length=8, max_length=240)
    timeout_seconds: int = Field(default=15, ge=1, le=300)
    max_retries: int = Field(default=2, ge=0, le=10)
    upstream_evidence_verified: bool = False
    active_policy_verified: bool = False
    workflow_dispatch_verified: bool = False
    risk_brain_blocked: bool = False

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class CommandAction(BaseModel):
    command: GatewayCommand
    actor: str = Field(..., min_length=1, max_length=120)
    approval_token: Optional[str] = Field(default=None, max_length=240)
    queue_receipt: Optional[str] = Field(default=None, max_length=240)
    dispatch_receipt: Optional[str] = Field(default=None, max_length=240)
    broker_receipt: Optional[str] = Field(default=None, max_length=240)
    reason: Optional[str] = Field(default=None, max_length=1000)


class CommandValidation(BaseModel):
    valid: bool
    violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    adapter: BrokerKind
    retry_backoff_seconds: List[int] = Field(default_factory=list)


class ExecutionCommandRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    workflow_record_id: str
    policy_record_id: str
    broker: BrokerKind
    account_id: str
    command_type: CommandType
    symbol: str
    side: str
    volume: float
    order_type: str
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_id: Optional[str] = None
    client_order_id: Optional[str] = None
    idempotency_key: str
    timeout_seconds: int
    max_retries: int
    state: CommandState
    validation: Optional[CommandValidation] = None
    approval_token: Optional[str] = None
    queue_receipt: Optional[str] = None
    dispatch_receipt: Optional[str] = None
    broker_receipt: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    record_id: str
    action: str
    actor: str
    from_state: Optional[CommandState] = None
    to_state: CommandState
    details: Dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
