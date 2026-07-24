from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AgentObjectiveState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    ALIGNED = "aligned"
    OBJECTIVE_DRIFT = "objective-drift"
    INTENT_CONFLICT = "intent-conflict"
    CONSTRAINT_ALERT = "constraint-alert"
    PRIORITY_CONFLICT = "priority-conflict"
    GOAL_HIJACK_ALERT = "goal-hijack-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AgentObjectiveObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    objective_id: str = Field(min_length=1, max_length=160)
    declared_objective_alignment: float = Field(ge=0.0, le=1.0)
    instruction_hierarchy_integrity: float = Field(ge=0.0, le=1.0)
    constraint_compliance: float = Field(ge=0.0, le=1.0)
    priority_consistency: float = Field(ge=0.0, le=1.0)
    human_intent_alignment: float = Field(ge=0.0, le=1.0)
    policy_intent_alignment: float = Field(ge=0.0, le=1.0)
    cross_agent_goal_consistency: float = Field(ge=0.0, le=1.0)
    goal_stability: float = Field(ge=0.0, le=1.0)
    explainability_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    objective_drift_events: int = Field(default=0, ge=0)
    conflicting_instruction_events: int = Field(default=0, ge=0)
    constraint_breach_events: int = Field(default=0, ge=0)
    priority_inversion_events: int = Field(default=0, ge=0)
    suspected_goal_hijack_events: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentObjectiveCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[AgentObjectiveObservation] = Field(min_length=1)
    min_objective_alignment: float = Field(default=0.85, ge=0.0, le=1.0)
    min_human_intent_alignment: float = Field(default=0.90, ge=0.0, le=1.0)
    min_constraint_compliance: float = Field(default=0.95, ge=0.0, le=1.0)
    min_goal_stability: float = Field(default=0.85, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.35, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_agent_objective_pairs(self):
        pairs = [(o.agent_id, o.objective_id) for o in self.observations]
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate agent/objective observation")
        return self


class AgentObjectiveDisposition(BaseModel):
    agent_id: str
    objective_id: str
    alignment_score: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class AgentObjectiveScores(BaseModel):
    objective_alignment: float = Field(ge=0.0, le=1.0)
    instruction_integrity: float = Field(ge=0.0, le=1.0)
    constraint_assurance: float = Field(ge=0.0, le=1.0)
    priority_consistency: float = Field(ge=0.0, le=1.0)
    human_intent_assurance: float = Field(ge=0.0, le=1.0)
    policy_intent_assurance: float = Field(ge=0.0, le=1.0)
    cross_agent_goal_consistency: float = Field(ge=0.0, le=1.0)
    goal_stability: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentObjectiveRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AgentObjectiveState
    scores: AgentObjectiveScores
    dispositions: List[AgentObjectiveDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class AgentObjectiveAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
