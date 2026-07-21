from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MT5ExecutionState(str, Enum):
    blocked = "blocked"
    bridge_required = "bridge-required"
    command_invalid = "command-invalid"
    risk_rejected = "risk-rejected"
    dispatch_required = "dispatch-required"
    broker_ack_pending = "broker-ack-pending"
    deal_ingestion_pending = "deal-ingestion-pending"
    partial_fill = "partial-fill"
    reconciliation_required = "reconciliation-required"
    execution_complete = "execution-complete"
    execution_failed = "execution-failed"


class MT5OrderObservation(BaseModel):
    bridge_state: str = "bridge-ready"
    command_schema_valid: bool = False
    symbol_mapping_verified: bool = False
    side_valid: bool = False
    requested_volume: float = Field(default=0.0, ge=0.0)
    normalized_volume: float = Field(default=0.0, ge=0.0)
    stop_loss_valid: bool = False
    take_profit_valid: bool = False
    price_deviation_within_budget: bool = False
    account_risk_clear: bool = False
    prop_rules_clear: bool = False
    idempotency_key_verified: bool = False
    command_dispatched: bool = False
    broker_acknowledged: bool = False
    broker_order_id: str | None = None
    broker_retcode_success: bool = False
    deal_events_received: int = Field(default=0, ge=0)
    requested_fill_volume: float = Field(default=0.0, ge=0.0)
    actual_fill_volume: float = Field(default=0.0, ge=0.0)
    average_fill_price_verified: bool = False
    position_ticket_verified: bool = False
    account_snapshot_reconciled: bool = False
    position_reconciled: bool = False
    pending_orders_reconciled: bool = False
    terminal_error_present: bool = False


class MT5ExecutionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=100)
    execution_id: UUID = Field(default_factory=uuid4)
    bridge_id: UUID
    account_reference: str = Field(min_length=1, max_length=200)
    symbol: str = Field(min_length=1, max_length=50)
    side: str = Field(min_length=1, max_length=20)
    risk_brain_clear: bool = True
    observation: MT5OrderObservation


class MT5ExecutionRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    execution_id: UUID
    bridge_id: UUID
    account_reference: str
    symbol: str
    side: str
    state: MT5ExecutionState
    reasons: list[str] = Field(default_factory=list)
    order_submission_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DispatchRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    execution_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    command_dispatched: bool
    broker_acknowledged: bool
    broker_order_id: str | None = None
    broker_retcode_success: bool
    deal_events_received: int = Field(default=0, ge=0)
    requested_fill_volume: float = Field(default=0.0, ge=0.0)
    actual_fill_volume: float = Field(default=0.0, ge=0.0)
    average_fill_price_verified: bool
    position_ticket_verified: bool
    account_snapshot_reconciled: bool
    position_reconciled: bool
    pending_orders_reconciled: bool
    terminal_error_present: bool = False


class MT5ExecutionStatusResponse(BaseModel):
    workspace_id: str
    records: int
    execution_complete: int
    blocked: int
    failed: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    execution_id: UUID
    state: MT5ExecutionState
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
