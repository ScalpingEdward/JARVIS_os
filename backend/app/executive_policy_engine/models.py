from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PolicyDecisionState(str, Enum):
    blocked = "blocked"
    policy_required = "policy-required"
    policy_denied = "policy-denied"
    approval_required = "approval-required"
    maintenance_mode = "maintenance-mode"
    dry_run_only = "dry-run-only"
    policy_approved = "policy-approved"
    ready_for_dispatch = "ready-for-dispatch"


class PolicyEffect(str, Enum):
    allow = "allow"
    deny = "deny"
    require_approval = "require-approval"
    dry_run = "dry-run"


class ActionKind(str, Enum):
    workflow_dispatch = "workflow-dispatch"
    executor_invocation = "executor-invocation"
    broker_order = "broker-order"
    position_close = "position-close"
    strategy_deployment = "strategy-deployment"
    capital_allocation = "capital-allocation"
    telegram_action = "telegram-action"
    vision_trigger = "vision-trigger"
    learning_update = "learning-update"
    portfolio_rebalance = "portfolio-rebalance"


class PolicyRule(BaseModel):
    policy_id: str = Field(min_length=1, max_length=120)
    version: int = Field(default=1, ge=1)
    priority: int = Field(default=100, ge=0, le=10000)
    action_kinds: list[ActionKind] = Field(default_factory=list)
    effect: PolicyEffect
    enabled: bool = True
    workspace_scope_verified: bool = False
    role_scope_verified: bool = False
    time_window_valid: bool = True
    emergency_rule: bool = False
    compliance_verified: bool = True


class PolicyObservation(BaseModel):
    policy_set_loaded: bool = False
    policy_version_resolved: bool = False
    inheritance_resolved: bool = False
    actor_role_resolved: bool = False
    action_context_valid: bool = False
    maintenance_mode_enabled: bool = False
    kill_switch_enabled: bool = False
    emergency_policy_active: bool = False
    dry_run_requested: bool = False
    human_approval_present: bool = False
    observability_context_linked: bool = False
    audit_sink_available: bool = False
    raw_policy_secrets_present: bool = False
    matched_rules: list[PolicyRule] = Field(default_factory=list)


class PolicyEnginePolicy(BaseModel):
    require_policy_set: bool = True
    require_version_resolution: bool = True
    require_inheritance_resolution: bool = True
    require_actor_role: bool = True
    require_action_context: bool = True
    require_observability_link: bool = True
    require_audit_sink: bool = True
    prohibit_raw_policy_secrets: bool = True
    deny_overrides_allow: bool = True
    emergency_rules_override_standard: bool = True
    maintenance_mode_blocks_mutations: bool = True
    kill_switch_blocks_all: bool = True


class PolicyEvaluationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    actor_role: str = Field(min_length=1, max_length=100)
    observability_assessment_id: str = Field(min_length=1, max_length=120)
    observability_state: str = Field(min_length=1, max_length=40)
    evaluation_id: UUID = Field(default_factory=uuid4)
    action_kind: ActionKind
    action_target: str = Field(min_length=1, max_length=240)
    mutating_action: bool = False
    observation: PolicyObservation = Field(default_factory=PolicyObservation)
    risk_brain_clear: bool = True
    policy: PolicyEnginePolicy = Field(default_factory=PolicyEnginePolicy)


class PolicyScores(BaseModel):
    policy_readiness: int = Field(ge=0, le=100)
    identity_integrity: int = Field(ge=0, le=100)
    rule_integrity: int = Field(ge=0, le=100)
    enforcement_integrity: int = Field(ge=0, le=100)
    audit_integrity: int = Field(ge=0, le=100)
    governance_confidence: int = Field(ge=0, le=100)


class PolicyEvaluation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    actor_role: str
    evaluation_id: UUID
    action_kind: ActionKind
    action_target: str
    state: PolicyDecisionState
    allowed: bool
    approval_required: bool
    dry_run_only: bool
    matched_policy_ids: list[str]
    recommended_action: str
    scores: PolicyScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PolicyEngineStatusResponse(BaseModel):
    workspace_id: str
    evaluations: int
    approved: int
    denied_or_blocked: int
    approval_required: int
    latest_state: PolicyDecisionState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    evaluation_record_id: UUID
    evaluation_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
