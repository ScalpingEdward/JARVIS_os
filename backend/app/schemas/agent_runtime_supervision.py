from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AgentRuntimeState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    HEALTHY = "healthy"
    BEHAVIOR_DRIFT = "behavior-drift"
    LOOP_ALERT = "loop-alert"
    TOOL_FAILURE_ALERT = "tool-failure-alert"
    BUDGET_ALERT = "budget-alert"
    INTERVENTION_REQUIRED = "intervention-required"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AgentRuntimeObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    runtime_id: str = Field(min_length=1, max_length=160)
    heartbeat_health: float = Field(ge=0.0, le=1.0)
    behavioral_stability: float = Field(ge=0.0, le=1.0)
    policy_conformance: float = Field(ge=0.0, le=1.0)
    tool_success_rate: float = Field(ge=0.0, le=1.0)
    output_validation_rate: float = Field(ge=0.0, le=1.0)
    human_override_readiness: float = Field(ge=0.0, le=1.0)
    stop_control_readiness: float = Field(ge=0.0, le=1.0)
    resource_efficiency: float = Field(ge=0.0, le=1.0)
    budget_headroom: float = Field(ge=0.0, le=1.0)
    context_integrity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    repeated_action_count: int = Field(default=0, ge=0)
    consecutive_tool_failures: int = Field(default=0, ge=0)
    policy_violation_count: int = Field(default=0, ge=0)
    human_override_failures: int = Field(default=0, ge=0)
    resource_spike_count: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentRuntimeCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[AgentRuntimeObservation] = Field(min_length=1)
    min_behavioral_stability: float = Field(default=0.80, ge=0.0, le=1.0)
    min_policy_conformance: float = Field(default=0.90, ge=0.0, le=1.0)
    min_tool_success_rate: float = Field(default=0.85, ge=0.0, le=1.0)
    min_stop_control_readiness: float = Field(default=0.95, ge=0.0, le=1.0)
    min_budget_headroom: float = Field(default=0.20, ge=0.0, le=1.0)
    max_repeated_actions: int = Field(default=8, ge=1)
    max_residual_risk: float = Field(default=0.35, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_runtime_observations(self):
        keys = [(o.agent_id, o.runtime_id) for o in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate agent/runtime observation")
        return self


class AgentRuntimeDisposition(BaseModel):
    agent_id: str
    agent_version: str
    runtime_id: str
    assurance_score: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class AgentRuntimeScores(BaseModel):
    runtime_health: float = Field(ge=0.0, le=1.0)
    behavioral_assurance: float = Field(ge=0.0, le=1.0)
    tool_reliability: float = Field(ge=0.0, le=1.0)
    intervention_readiness: float = Field(ge=0.0, le=1.0)
    resource_resilience: float = Field(ge=0.0, le=1.0)
    context_integrity: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentRuntimeRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AgentRuntimeState
    scores: AgentRuntimeScores
    dispositions: List[AgentRuntimeDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class AgentRuntimeAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
