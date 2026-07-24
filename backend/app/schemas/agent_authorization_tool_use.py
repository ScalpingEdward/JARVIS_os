from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AgentAuthorizationState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    AUTHORIZED = "authorized"
    SCOPE_ALERT = "scope-alert"
    TOOL_ALERT = "tool-alert"
    DELEGATION_ALERT = "delegation-alert"
    INJECTION_ALERT = "injection-alert"
    DATA_ACCESS_ALERT = "data-access-alert"
    AUTONOMY_ALERT = "autonomy-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AgentToolObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=120)
    tool_name: str = Field(min_length=1, max_length=160)
    tool_category: str = Field(min_length=1, max_length=120)
    requested_scope: float = Field(ge=0.0, le=1.0)
    approved_scope: float = Field(ge=0.0, le=1.0)
    least_privilege_score: float = Field(ge=0.0, le=1.0)
    authorization_coverage: float = Field(ge=0.0, le=1.0)
    human_approval_coverage: float = Field(ge=0.0, le=1.0)
    tool_allowlist_coverage: float = Field(ge=0.0, le=1.0)
    delegation_control_score: float = Field(ge=0.0, le=1.0)
    prompt_injection_resilience: float = Field(ge=0.0, le=1.0)
    data_access_control_score: float = Field(ge=0.0, le=1.0)
    output_validation_score: float = Field(ge=0.0, le=1.0)
    auditability_score: float = Field(ge=0.0, le=1.0)
    reversibility_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    unauthorized_tool_attempts: int = Field(default=0, ge=0)
    unapproved_delegations: int = Field(default=0, ge=0)
    prompt_injection_events: int = Field(default=0, ge=0)
    sensitive_data_access_events: int = Field(default=0, ge=0)
    autonomous_high_impact_actions: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentAuthorizationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[AgentToolObservation] = Field(min_length=1)
    min_least_privilege_score: float = Field(default=0.80, ge=0.0, le=1.0)
    min_authorization_coverage: float = Field(default=0.90, ge=0.0, le=1.0)
    min_human_approval_coverage: float = Field(default=0.95, ge=0.0, le=1.0)
    min_prompt_injection_resilience: float = Field(default=0.80, ge=0.0, le=1.0)
    max_scope_excess: float = Field(default=0.10, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.35, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_agent_tool_pairs(self):
        pairs = [(o.agent_id, o.tool_name) for o in self.observations]
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate agent/tool observation")
        return self


class AgentToolDisposition(BaseModel):
    agent_id: str
    agent_version: str
    tool_name: str
    assurance_score: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class AgentAuthorizationScores(BaseModel):
    identity_and_scope_assurance: float = Field(ge=0.0, le=1.0)
    tool_control_assurance: float = Field(ge=0.0, le=1.0)
    delegation_assurance: float = Field(ge=0.0, le=1.0)
    injection_resilience: float = Field(ge=0.0, le=1.0)
    data_access_assurance: float = Field(ge=0.0, le=1.0)
    human_control_assurance: float = Field(ge=0.0, le=1.0)
    audit_and_reversibility: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentAuthorizationRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AgentAuthorizationState
    scores: AgentAuthorizationScores
    dispositions: List[AgentToolDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class AgentAuthorizationAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
