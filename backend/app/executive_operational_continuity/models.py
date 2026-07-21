from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ContinuityState(str, Enum):
    blocked = "blocked"
    copy_sync_required = "copy-sync-required"
    health_degraded = "health-degraded"
    failover_approval_required = "failover-approval-required"
    failover_pending = "failover-pending"
    reconciliation_required = "reconciliation-required"
    continuity_ready = "continuity-ready"
    failed_over = "failed-over"
    recovered = "recovered"


class ContinuityObservation(BaseModel):
    copy_execution_state: str = Field(default="synchronized", min_length=1, max_length=50)
    source_account_healthy: bool = True
    follower_accounts_healthy: bool = True
    broker_sessions_healthy: bool = True
    market_data_healthy: bool = True
    executor_healthy: bool = True
    heartbeat_fresh: bool = True
    primary_vps_healthy: bool = True
    standby_vps_ready: bool = True
    state_checkpoint_current: bool = True
    failover_requested: bool = False
    human_approval_verified: bool = False
    failover_dispatched: bool = False
    failover_acknowledged: bool = False
    active_node_matches_expected: bool = True
    positions_reconciled: bool = True
    pending_orders_reconciled: bool = True
    copy_group_reconciled: bool = True
    recovery_requested: bool = False
    recovery_human_approved: bool = False
    primary_restored: bool = True


class ContinuityPolicy(BaseModel):
    require_synchronized_copy: bool = True
    require_healthy_runtime: bool = True
    require_standby: bool = True
    require_current_checkpoint: bool = True
    require_human_approval_for_failover: bool = True
    require_final_reconciliation: bool = True
    require_human_approval_for_recovery: bool = True


class ContinuityAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    continuity_id: UUID = Field(default_factory=uuid4)
    copy_group_id: UUID
    primary_node: str = Field(min_length=1, max_length=180)
    standby_node: str = Field(min_length=1, max_length=180)
    observation: ContinuityObservation
    risk_brain_clear: bool = True
    policy: ContinuityPolicy = Field(default_factory=ContinuityPolicy)


class ContinuityAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    continuity_id: UUID
    copy_group_id: UUID
    primary_node: str
    standby_node: str
    state: ContinuityState
    failover_required: bool
    active_node: str
    reconciled: bool
    recommended_action: str
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FailoverRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    continuity_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    human_approval_verified: bool = False
    failover_acknowledged: bool = True
    active_node: str = Field(min_length=1, max_length=180)
    final_reconciliation_complete: bool = True


class RecoveryRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    continuity_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    human_approval_verified: bool = False
    primary_restored: bool = True
    active_node: str = Field(min_length=1, max_length=180)
    final_reconciliation_complete: bool = True


class ContinuityStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    healthy: int
    failed_over: int
    attention_required: int
    latest_state: ContinuityState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    record_id: UUID
    continuity_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
