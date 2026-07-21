from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MT5PositionLifecycleState(str, Enum):
    blocked = "blocked"
    execution_required = "execution-required"
    position_missing = "position-missing"
    request_invalid = "request-invalid"
    protection_invalid = "protection-invalid"
    approval_required = "approval-required"
    command_pending = "command-pending"
    broker_ack_pending = "broker-ack-pending"
    deal_event_pending = "deal-event-pending"
    partial_close = "partial-close"
    reconciliation_required = "reconciliation-required"
    lifecycle_complete = "lifecycle-complete"
    lifecycle_failed = "lifecycle-failed"


class PositionLifecycleObservation(BaseModel):
    execution_state: str = "execution-complete"
    position_exists: bool = False
    position_ticket: int = Field(default=0, ge=0)
    symbol: str = Field(default="", max_length=40)
    current_volume: float = Field(default=0.0, ge=0)
    action: str = "modify"
    requested_volume: float = Field(default=0.0, ge=0)
    requested_stop_loss: float | None = Field(default=None, ge=0)
    requested_take_profit: float | None = Field(default=None, ge=0)
    price_precision_valid: bool = False
    volume_step_valid: bool = False
    stop_level_valid: bool = False
    freeze_level_clear: bool = False
    risk_policy_clear: bool = False
    prop_rule_clear: bool = False
    human_approval_verified: bool = False
    command_dispatched: bool = False
    broker_acknowledged: bool = False
    broker_retcode_success: bool = False
    deal_event_ingested: bool = False
    closed_volume: float = Field(default=0.0, ge=0)
    remaining_volume: float = Field(default=0.0, ge=0)
    resulting_stop_loss_verified: bool = False
    resulting_take_profit_verified: bool = False
    position_reconciled: bool = False
    account_snapshot_reconciled: bool = False
    terminal_error: bool = False


class MT5PositionLifecycleCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=100)
    lifecycle_id: UUID = Field(default_factory=uuid4)
    risk_brain_clear: bool = True
    observation: PositionLifecycleObservation


class MT5PositionLifecycleRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    lifecycle_id: UUID
    position_ticket: int
    symbol: str
    action: str
    state: MT5PositionLifecycleState
    reasons: list[str] = Field(default_factory=list)
    position_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PositionActionRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    lifecycle_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    human_approval_verified: bool
    command_dispatched: bool
    broker_acknowledged: bool
    broker_retcode_success: bool
    deal_event_ingested: bool
    closed_volume: float = Field(default=0.0, ge=0)
    remaining_volume: float = Field(default=0.0, ge=0)
    resulting_stop_loss_verified: bool
    resulting_take_profit_verified: bool
    position_reconciled: bool
    account_snapshot_reconciled: bool
    terminal_error: bool = False


class PositionLifecycleStatusResponse(BaseModel):
    workspace_id: str
    records: int
    lifecycle_complete: int
    blocked: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    lifecycle_id: UUID
    state: MT5PositionLifecycleState
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
