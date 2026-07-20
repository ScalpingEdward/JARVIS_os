from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ExecutionState(str, Enum):
    blocked = "blocked"
    intent_required = "intent-required"
    approval_required = "approval-required"
    adapter_unavailable = "adapter-unavailable"
    dispatch_failed = "dispatch-failed"
    acknowledgement_pending = "acknowledgement-pending"
    partial_fill = "partial-fill"
    reconciliation_required = "reconciliation-required"
    execution_completed = "execution-completed"


class ExecutionAdapter(str, Enum):
    mt5 = "mt5"
    mt4 = "mt4"
    dxtrade = "dxtrade"
    ctrader = "ctrader"
    interactive_brokers = "interactive-brokers"
    fix_gateway = "fix-gateway"
    rest = "rest"
    paper = "paper"
    simulation = "simulation"


class ExecutionObservation(BaseModel):
    order_intent_state: str = Field(default="ready-for-dispatch", min_length=1, max_length=40)
    human_approval_verified: bool = True
    adapter_registered: bool = True
    adapter_healthy: bool = True
    credential_binding_valid: bool = True
    idempotency_key_present: bool = True
    dispatch_attempted: bool = True
    dispatch_succeeded: bool = True
    broker_acknowledged: bool = True
    broker_order_id_present: bool = True
    requested_quantity: float = Field(gt=0)
    filled_quantity: float = Field(ge=0)
    average_fill_price: float | None = Field(default=None, gt=0)
    expected_price: float | None = Field(default=None, gt=0)
    maximum_slippage_bps: float = Field(default=25, ge=0)
    commission_reported: bool = True
    fill_events_complete: bool = True
    duplicate_fill_detected: bool = False
    execution_timeout: bool = False
    cancel_required: bool = False
    cancel_acknowledged: bool = True
    broker_position_reconciled: bool = True


class ExecutionPolicy(BaseModel):
    require_ready_intent: bool = True
    require_human_approval: bool = True
    require_registered_adapter: bool = True
    require_healthy_adapter: bool = True
    require_credential_binding: bool = True
    require_idempotency_key: bool = True
    require_broker_ack: bool = True
    require_broker_order_id: bool = True
    require_complete_fill_events: bool = True
    require_commission: bool = True
    prohibit_duplicate_fills: bool = True
    require_position_reconciliation: bool = True


class ExecutionAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    execution_id: UUID = Field(default_factory=uuid4)
    order_intent_id: UUID
    adapter: ExecutionAdapter
    account_reference: str = Field(min_length=1, max_length=180)
    canonical_symbol: str = Field(min_length=1, max_length=80)
    idempotency_key: str = Field(min_length=1, max_length=180)
    observation: ExecutionObservation
    risk_brain_clear: bool = True
    policy: ExecutionPolicy = Field(default_factory=ExecutionPolicy)


class ExecutionAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    execution_id: UUID
    order_intent_id: UUID
    adapter: ExecutionAdapter
    account_reference: str
    canonical_symbol: str
    idempotency_key: str
    state: ExecutionState
    dispatched: bool
    broker_acknowledged: bool
    fill_ratio: float
    reconciliation_complete: bool
    recommended_action: str
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReconcileRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    execution_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    broker_position_reconciled: bool = True
    fill_events_complete: bool = True


class ExecutionStatusResponse(BaseModel):
    workspace_id: str
    executions: int
    completed: int
    pending_or_failed: int
    latest_state: ExecutionState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    execution_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
