from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class BreakEvenState(str, Enum):
    BLOCKED = "blocked"
    TRAILING_REQUIRED = "trailing-required"
    POSITION_MISSING = "position-missing"
    TRIGGER_NOT_REACHED = "trigger-not-reached"
    BREAK_EVEN_INVALID = "break-even-invalid"
    SCALE_OUT_INVALID = "scale-out-invalid"
    RISK_REJECTED = "risk-rejected"
    APPROVAL_REQUIRED = "approval-required"
    COMMAND_PENDING = "command-pending"
    BROKER_ACK_PENDING = "broker-ack-pending"
    DEAL_EVENT_PENDING = "deal-event-pending"
    RECONCILIATION_REQUIRED = "reconciliation-required"
    PROFIT_LOCKED = "profit-locked"
    FAILED = "failed"


class BreakEvenAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=200)
    lifecycle_id: str = Field(min_length=1, max_length=200)
    trailing_state: str
    position_ticket: int
    side: str
    entry_price: float = Field(gt=0)
    current_price: float = Field(gt=0)
    current_volume: float = Field(gt=0)
    point_size: float = Field(gt=0)
    trigger_points: float = Field(gt=0)
    break_even_offset_points: float = Field(ge=0)
    spread_points: float = Field(ge=0)
    commission_points: float = Field(ge=0)
    scale_out_percent: int = Field(default=0, ge=0, le=100)
    volume_step: float = Field(gt=0)
    minimum_remaining_volume: float = Field(ge=0)
    minimum_rr: float = Field(ge=0)
    observed_rr: float = Field(ge=0)
    stop_level_points: float = Field(ge=0)
    freeze_level_points: float = Field(ge=0)
    risk_approved: bool
    prop_rules_approved: bool
    risk_brain_blocked: bool = False
    human_approved: bool = False
    command_dispatched: bool = False
    broker_acknowledged: bool = False
    broker_retcode: int | None = None
    deal_event_received: bool = False
    resulting_stop_loss: float | None = None
    resulting_volume: float | None = None
    position_reconciled: bool = False
    account_reconciled: bool = False
    terminal_error: str | None = None


class BreakEvenAssessment(BreakEvenAssessmentCreate):
    id: UUID = Field(default_factory=uuid4)
    state: BreakEvenState
    proposed_stop_loss: float | None = None
    close_volume: float = 0.0
    remaining_volume: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BreakEvenListResponse(BaseModel):
    items: list[BreakEvenAssessment]
    count: int


class BreakEvenStatusResponse(BaseModel):
    workspace_id: str
    module: str = "executive-mt5-break-even-scale-out"
    version: str = "18.90"
    assessments: int


class AuditRecord(BaseModel):
    workspace_id: str
    record_id: UUID
    action: str
    state: BreakEvenState
    actor_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
