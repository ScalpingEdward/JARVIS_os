from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CopyGovernanceState(str, Enum):
    blocked = "blocked"
    reentry_required = "reentry-required"
    topology_invalid = "topology-invalid"
    account_unavailable = "account-unavailable"
    policy_rejected = "policy-rejected"
    risk_mismatch = "risk-mismatch"
    synchronization_degraded = "synchronization-degraded"
    approval_required = "approval-required"
    copy_ready = "copy-ready"
    copy_suspended = "copy-suspended"


class AccountRole(str, Enum):
    source = "source"
    follower = "follower"


class CopyMode(str, Enum):
    disabled = "disabled"
    fixed_lot = "fixed-lot"
    balance_ratio = "balance-ratio"
    equity_ratio = "equity-ratio"
    risk_ratio = "risk-ratio"


class AccountBinding(BaseModel):
    account_reference: str = Field(min_length=1, max_length=180)
    broker_reference: str = Field(min_length=1, max_length=180)
    role: AccountRole
    enabled: bool = True
    session_ready: bool = True
    account_risk_state: str = Field(default="account-risk-clear", min_length=1, max_length=50)
    emergency_containment_state: str = Field(default="released", min_length=1, max_length=50)
    controlled_reentry_state: str = Field(default="trading-reenabled", min_length=1, max_length=50)
    balance: float = Field(gt=0)
    equity: float = Field(gt=0)
    maximum_daily_loss_pct: float = Field(default=4.0, gt=0)
    maximum_drawdown_pct: float = Field(default=10.0, gt=0)
    current_open_risk_pct: float = Field(default=0, ge=0)
    maximum_open_risk_pct: float = Field(default=3.0, gt=0)
    symbol_allowlist: list[str] = Field(default_factory=list)


class CopyGovernanceObservation(BaseModel):
    source_signal_present: bool = True
    source_order_intent_approved: bool = True
    source_execution_reconciled: bool = True
    source_position_reconciled: bool = True
    follower_sessions_ready: bool = True
    symbol_mapping_complete: bool = True
    volume_mapping_complete: bool = True
    stop_mapping_complete: bool = True
    direction_consistent: bool = True
    latency_ms: float = Field(default=100, ge=0)
    maximum_latency_ms: float = Field(default=1000, gt=0)
    divergence_pct: float = Field(default=0, ge=0)
    maximum_divergence_pct: float = Field(default=2.0, gt=0)
    duplicate_dispatch_detected: bool = False
    cross_account_hedge_detected: bool = False
    prop_rule_conflict_detected: bool = False
    human_approval_verified: bool = False
    suspension_requested: bool = False


class CopyGovernancePolicy(BaseModel):
    require_trading_reenabled: bool = True
    require_single_source: bool = True
    minimum_followers: int = Field(default=1, ge=1)
    maximum_followers: int = Field(default=20, ge=1)
    require_account_risk_clear: bool = True
    prohibit_cross_account_hedging: bool = True
    prohibit_duplicate_dispatch: bool = True
    require_prop_rule_compatibility: bool = True
    require_human_approval: bool = True
    maximum_total_open_risk_pct: float = Field(default=6.0, gt=0)


class CopyGovernanceAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    copy_group_id: UUID = Field(default_factory=uuid4)
    copy_mode: CopyMode
    accounts: list[AccountBinding] = Field(min_length=2, max_length=21)
    observation: CopyGovernanceObservation
    risk_brain_clear: bool = True
    policy: CopyGovernancePolicy = Field(default_factory=CopyGovernancePolicy)


class CopyGovernanceAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    copy_group_id: UUID
    copy_mode: CopyMode
    source_account_reference: str | None
    follower_count: int
    aggregate_open_risk_pct: float
    state: CopyGovernanceState
    synchronized: bool
    approved: bool
    recommended_action: str
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CopyControlRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    copy_group_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    human_approval_verified: bool = False
    synchronization_verified: bool = True
    account_risk_clear: bool = True


class CopyGovernanceStatusResponse(BaseModel):
    workspace_id: str
    groups: int
    ready: int
    suspended: int
    attention_required: int
    latest_state: CopyGovernanceState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    record_id: UUID
    copy_group_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
