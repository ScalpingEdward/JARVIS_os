from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PositionLifecycleState(str, Enum):
    blocked = "blocked"
    execution_required = "execution-required"
    reconciliation_required = "reconciliation-required"
    protection_required = "protection-required"
    modification_approval_required = "modification-approval-required"
    close_pending = "close-pending"
    broker_mismatch = "broker-mismatch"
    position_open = "position-open"
    position_closed = "position-closed"


class PositionSide(str, Enum):
    buy = "buy"
    sell = "sell"


class PositionLifecycleObservation(BaseModel):
    execution_state: str = Field(default="execution-completed", min_length=1, max_length=40)
    broker_position_present: bool = True
    broker_position_id_present: bool = True
    broker_symbol_matches: bool = True
    broker_side_matches: bool = True
    broker_quantity_matches: bool = True
    open_price_reconciled: bool = True
    commission_reconciled: bool = True
    stop_loss_present: bool = True
    take_profit_present: bool = True
    protection_acknowledged: bool = True
    modification_requested: bool = False
    modification_human_approved: bool = False
    modification_acknowledged: bool = True
    close_requested: bool = False
    close_human_approved: bool = False
    close_acknowledged: bool = True
    remaining_quantity: float = Field(default=0, ge=0)
    realized_pnl_reported: bool = True
    swap_reported: bool = True
    final_broker_reconciled: bool = True


class PositionLifecyclePolicy(BaseModel):
    require_completed_execution: bool = True
    require_broker_position: bool = True
    require_position_identity: bool = True
    require_open_reconciliation: bool = True
    require_stop_loss: bool = True
    require_take_profit: bool = False
    require_protection_acknowledgement: bool = True
    require_human_approval_for_modification: bool = True
    require_human_approval_for_close: bool = True
    require_final_reconciliation: bool = True


class PositionLifecycleAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    position_id: UUID = Field(default_factory=uuid4)
    execution_id: UUID
    broker_position_id: str = Field(min_length=1, max_length=180)
    account_reference: str = Field(min_length=1, max_length=180)
    canonical_symbol: str = Field(min_length=1, max_length=80)
    side: PositionSide
    opened_quantity: float = Field(gt=0)
    observation: PositionLifecycleObservation
    risk_brain_clear: bool = True
    policy: PositionLifecyclePolicy = Field(default_factory=PositionLifecyclePolicy)


class PositionLifecycleAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    position_id: UUID
    execution_id: UUID
    broker_position_id: str
    account_reference: str
    canonical_symbol: str
    side: PositionSide
    opened_quantity: float
    state: PositionLifecycleState
    protected: bool
    reconciled: bool
    closed: bool
    recommended_action: str
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PositionActionRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    position_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    human_approval_verified: bool = False
    broker_acknowledged: bool = True
    final_broker_reconciled: bool = True
    remaining_quantity: float = Field(default=0, ge=0)


class PositionLifecycleStatusResponse(BaseModel):
    workspace_id: str
    positions: int
    open_positions: int
    closed_positions: int
    attention_required: int
    latest_state: PositionLifecycleState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    position_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
