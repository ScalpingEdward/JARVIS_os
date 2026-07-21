from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PositionStreamState(str, Enum):
    blocked = "blocked"
    lifecycle_required = "lifecycle-required"
    stream_unavailable = "stream-unavailable"
    event_gap_detected = "event-gap-detected"
    stale_snapshot = "stale-snapshot"
    trailing_inactive = "trailing-inactive"
    trigger_not_reached = "trigger-not-reached"
    protection_invalid = "protection-invalid"
    approval_required = "approval-required"
    modify_pending = "modify-pending"
    broker_ack_pending = "broker-ack-pending"
    reconciliation_required = "reconciliation-required"
    trailing_active = "trailing-active"
    trailing_failed = "trailing-failed"


class PositionStreamObservation(BaseModel):
    lifecycle_state: str = "lifecycle-complete"
    stream_connected: bool = False
    sequence_contiguous: bool = False
    snapshot_age_seconds: int = Field(default=9999, ge=0)
    max_snapshot_age_seconds: int = Field(default=10, ge=1)
    position_exists: bool = True
    symbol: str = Field(min_length=1, max_length=50)
    side: str = "buy"
    current_price: float = Field(gt=0)
    entry_price: float = Field(gt=0)
    current_stop_loss: float | None = None
    current_take_profit: float | None = None
    trailing_enabled: bool = False
    activation_distance_points: int = Field(default=0, ge=0)
    trailing_distance_points: int = Field(default=0, ge=0)
    point_size: float = Field(default=0.00001, gt=0)
    stop_level_points: int = Field(default=0, ge=0)
    freeze_level_points: int = Field(default=0, ge=0)
    proposed_stop_loss: float | None = None
    human_approval_verified: bool = False
    modify_dispatched: bool = False
    modify_acknowledged: bool = False
    broker_retcode_ok: bool = False
    resulting_stop_loss_verified: bool = False
    position_snapshot_reconciled: bool = False
    account_snapshot_reconciled: bool = False
    terminal_error: str | None = None


class PositionStreamCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=100)
    stream_id: UUID = Field(default_factory=uuid4)
    position_ticket: int = Field(gt=0)
    risk_brain_clear: bool = True
    account_risk_clear: bool = True
    prop_rules_clear: bool = True
    observation: PositionStreamObservation


class PositionStreamRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    stream_id: UUID
    position_ticket: int
    state: PositionStreamState
    reasons: list[str] = Field(default_factory=list)
    trailing_commands_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TrailingModifyRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    stream_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    human_approval_verified: bool
    modify_dispatched: bool
    modify_acknowledged: bool
    broker_retcode_ok: bool
    resulting_stop_loss_verified: bool
    position_snapshot_reconciled: bool
    account_snapshot_reconciled: bool
    terminal_error: str | None = None


class PositionStreamStatusResponse(BaseModel):
    workspace_id: str
    records: int
    trailing_active: int
    blocked: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    stream_id: UUID
    state: PositionStreamState
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
