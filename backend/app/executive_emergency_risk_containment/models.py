from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EmergencyContainmentState(str, Enum):
    blocked = "blocked"
    account_risk_required = "account-risk-required"
    trigger_not_confirmed = "trigger-not-confirmed"
    approval_required = "approval-required"
    cancellation_pending = "cancellation-pending"
    liquidation_pending = "liquidation-pending"
    reconciliation_required = "reconciliation-required"
    contained = "contained"
    released = "released"


class EmergencyTrigger(str, Enum):
    daily_loss = "daily-loss"
    maximum_drawdown = "maximum-drawdown"
    margin_stress = "margin-stress"
    broker_disconnect = "broker-disconnect"
    market_data_failure = "market-data-failure"
    duplicate_execution = "duplicate-execution"
    manual_kill_switch = "manual-kill-switch"


class EmergencyContainmentObservation(BaseModel):
    account_risk_state: str = Field(default="daily-loss-breached", min_length=1, max_length=50)
    trigger_confirmed: bool = True
    kill_switch_active: bool = True
    new_order_block_active: bool = True
    pending_orders_present: bool = False
    pending_orders_cancelled: bool = True
    open_positions_present: bool = True
    human_approval_verified: bool = False
    liquidation_dispatched: bool = False
    liquidation_acknowledged: bool = False
    remaining_open_positions: int = Field(default=0, ge=0)
    remaining_pending_orders: int = Field(default=0, ge=0)
    broker_equity_reconciled: bool = True
    broker_balance_reconciled: bool = True
    position_state_reconciled: bool = True
    incident_recorded: bool = True
    release_requested: bool = False
    release_human_approved: bool = False
    controls_reset_acknowledged: bool = True


class EmergencyContainmentPolicy(BaseModel):
    require_account_risk_breach: bool = True
    require_confirmed_trigger: bool = True
    require_kill_switch: bool = True
    require_new_order_block: bool = True
    cancel_pending_orders: bool = True
    require_human_approval_for_liquidation: bool = True
    require_zero_remaining_positions: bool = True
    require_zero_remaining_orders: bool = True
    require_final_reconciliation: bool = True
    require_incident_record: bool = True
    require_human_approval_for_release: bool = True


class EmergencyContainmentAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    containment_id: UUID = Field(default_factory=uuid4)
    account_reference: str = Field(min_length=1, max_length=180)
    broker_reference: str = Field(min_length=1, max_length=180)
    trigger: EmergencyTrigger
    observation: EmergencyContainmentObservation
    risk_brain_clear: bool = True
    policy: EmergencyContainmentPolicy = Field(default_factory=EmergencyContainmentPolicy)


class EmergencyContainmentAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    containment_id: UUID
    account_reference: str
    broker_reference: str
    trigger: EmergencyTrigger
    state: EmergencyContainmentState
    kill_switch_active: bool
    new_orders_blocked: bool
    pending_orders_cancelled: bool
    positions_liquidated: bool
    reconciled: bool
    recommended_action: str
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContainmentActionRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    containment_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    human_approval_verified: bool = False
    pending_orders_cancelled: bool = True
    liquidation_acknowledged: bool = True
    remaining_open_positions: int = Field(default=0, ge=0)
    remaining_pending_orders: int = Field(default=0, ge=0)
    final_reconciliation_complete: bool = True


class ContainmentReleaseRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    containment_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    human_approval_verified: bool = False
    account_risk_state: str = Field(default="account-risk-clear", min_length=1, max_length=50)
    controls_reset_acknowledged: bool = True


class EmergencyContainmentStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    active: int
    contained: int
    released: int
    latest_state: EmergencyContainmentState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    record_id: UUID
    containment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
