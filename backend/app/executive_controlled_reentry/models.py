from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ControlledReentryState(str, Enum):
    blocked = "blocked"
    containment_release_required = "containment-release-required"
    account_reconciliation_required = "account-reconciliation-required"
    cooldown_active = "cooldown-active"
    readiness_required = "readiness-required"
    approval_required = "approval-required"
    canary_required = "canary-required"
    canary_failed = "canary-failed"
    limited_trading = "limited-trading"
    trading_reenabled = "trading-reenabled"


class ControlledReentryObservation(BaseModel):
    containment_state: str = Field(default="released", min_length=1, max_length=50)
    account_risk_state: str = Field(default="account-risk-clear", min_length=1, max_length=50)
    broker_session_ready: bool = True
    market_data_ready: bool = True
    positions_reconciled: bool = True
    pending_orders_reconciled: bool = True
    incident_review_completed: bool = True
    root_cause_identified: bool = True
    remediation_verified: bool = True
    cooldown_elapsed_minutes: int = Field(default=60, ge=0)
    human_approval_verified: bool = False
    canary_requested: bool = True
    canary_dispatched: bool = False
    canary_acknowledged: bool = False
    canary_risk_pct: float = Field(default=0.25, ge=0)
    canary_orders: int = Field(default=0, ge=0)
    canary_failures: int = Field(default=0, ge=0)
    canary_slippage_bps: float = Field(default=0, ge=0)
    canary_reconciliation_complete: bool = True
    full_reenable_requested: bool = False
    full_reenable_human_approved: bool = False


class ControlledReentryPolicy(BaseModel):
    require_released_containment: bool = True
    require_account_risk_clear: bool = True
    require_broker_reconciliation: bool = True
    require_incident_review: bool = True
    minimum_cooldown_minutes: int = Field(default=60, ge=0)
    require_human_approval: bool = True
    require_canary: bool = True
    maximum_canary_risk_pct: float = Field(default=0.5, gt=0)
    maximum_canary_orders: int = Field(default=3, gt=0)
    maximum_canary_failures: int = Field(default=0, ge=0)
    maximum_canary_slippage_bps: float = Field(default=30, ge=0)
    require_canary_reconciliation: bool = True
    require_human_approval_for_full_reenable: bool = True


class ControlledReentryAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    reentry_id: UUID = Field(default_factory=uuid4)
    containment_id: UUID
    account_reference: str = Field(min_length=1, max_length=180)
    broker_reference: str = Field(min_length=1, max_length=180)
    observation: ControlledReentryObservation
    risk_brain_clear: bool = True
    policy: ControlledReentryPolicy = Field(default_factory=ControlledReentryPolicy)


class ControlledReentryAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    reentry_id: UUID
    containment_id: UUID
    account_reference: str
    broker_reference: str
    state: ControlledReentryState
    canary_risk_pct: float
    canary_orders: int
    canary_failures: int
    new_orders_enabled: bool
    full_trading_enabled: bool
    recommended_action: str
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CanaryResultRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    reentry_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    human_approval_verified: bool = False
    canary_dispatched: bool = True
    canary_acknowledged: bool = True
    canary_orders: int = Field(default=1, ge=0)
    canary_failures: int = Field(default=0, ge=0)
    canary_slippage_bps: float = Field(default=0, ge=0)
    reconciliation_complete: bool = True


class FullReenableRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    reentry_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    human_approval_verified: bool = False
    account_risk_state: str = Field(default="account-risk-clear", min_length=1, max_length=50)
    broker_session_ready: bool = True
    market_data_ready: bool = True


class ControlledReentryStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    blocked_or_waiting: int
    limited: int
    fully_reenabled: int
    latest_state: ControlledReentryState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    record_id: UUID
    reentry_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
