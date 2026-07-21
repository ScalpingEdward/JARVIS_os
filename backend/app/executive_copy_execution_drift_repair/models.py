from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CopyExecutionState(str, Enum):
    blocked = "blocked"
    copy_governance_required = "copy-governance-required"
    source_execution_required = "source-execution-required"
    fanout_pending = "fanout-pending"
    follower_ack_pending = "follower-ack-pending"
    drift_detected = "drift-detected"
    repair_approval_required = "repair-approval-required"
    repair_pending = "repair-pending"
    synchronized = "synchronized"
    quarantined = "quarantined"


class FollowerExecutionEvidence(BaseModel):
    account_reference: str = Field(min_length=1, max_length=180)
    intended: bool = True
    dispatch_attempted: bool = True
    broker_acknowledged: bool = True
    broker_order_id_present: bool = True
    symbol_matches: bool = True
    side_matches: bool = True
    volume_matches: bool = True
    stop_loss_matches: bool = True
    take_profit_matches: bool = True
    position_present: bool = True
    fill_price_drift_bps: float = Field(default=0, ge=0)
    volume_drift_pct: float = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    duplicate_execution_detected: bool = False
    repair_required: bool = False
    repair_human_approved: bool = False
    repair_dispatched: bool = False
    repair_acknowledged: bool = False
    quarantined: bool = False


class CopyExecutionObservation(BaseModel):
    copy_governance_state: str = Field(default="copy-ready", min_length=1, max_length=50)
    source_execution_state: str = Field(default="execution-completed", min_length=1, max_length=50)
    source_position_state: str = Field(default="position-open", min_length=1, max_length=50)
    fanout_requested: bool = True
    source_execution_reconciled: bool = True
    followers: list[FollowerExecutionEvidence] = Field(min_length=1, max_length=50)


class CopyExecutionPolicy(BaseModel):
    require_copy_ready: bool = True
    require_source_execution_completed: bool = True
    require_source_position_open: bool = True
    require_all_intended_followers: bool = True
    require_broker_acknowledgement: bool = True
    maximum_latency_ms: int = Field(default=1500, ge=0)
    maximum_fill_price_drift_bps: float = Field(default=35, ge=0)
    maximum_volume_drift_pct: float = Field(default=5, ge=0)
    require_symbol_side_volume_mapping: bool = True
    require_protection_mapping: bool = True
    prohibit_duplicate_execution: bool = True
    require_human_approval_for_repair: bool = True


class CopyExecutionAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    fanout_id: UUID = Field(default_factory=uuid4)
    copy_group_id: UUID
    source_execution_id: UUID
    source_account_reference: str = Field(min_length=1, max_length=180)
    canonical_symbol: str = Field(min_length=1, max_length=80)
    observation: CopyExecutionObservation
    risk_brain_clear: bool = True
    policy: CopyExecutionPolicy = Field(default_factory=CopyExecutionPolicy)


class CopyExecutionAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    fanout_id: UUID
    copy_group_id: UUID
    source_execution_id: UUID
    source_account_reference: str
    canonical_symbol: str
    state: CopyExecutionState
    intended_followers: int
    acknowledged_followers: int
    synchronized_followers: int
    drifted_followers: int
    quarantined_followers: int
    recommended_action: str
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DriftRepairRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    fanout_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    human_approval_verified: bool = False
    repaired_accounts: list[str] = Field(default_factory=list, max_length=50)
    repair_dispatch_acknowledged: bool = True
    final_positions_reconciled: bool = True
    remaining_drifted_followers: int = Field(default=0, ge=0)


class CopyExecutionStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    synchronized: int
    attention_required: int
    quarantined: int
    latest_state: CopyExecutionState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    record_id: UUID
    fanout_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
