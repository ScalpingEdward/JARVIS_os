from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class MultiAgentCoordinationState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    COORDINATED = "coordinated"
    ROLE_CONFLICT = "role-conflict"
    DELEGATION_ALERT = "delegation-alert"
    CONSENSUS_ALERT = "consensus-alert"
    DEADLOCK_ALERT = "deadlock-alert"
    HANDOFF_ALERT = "handoff-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AgentCoordinationObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=120)
    authority_scope: float = Field(ge=0.0, le=1.0)
    responsibility_clarity: float = Field(ge=0.0, le=1.0)
    delegation_integrity: float = Field(ge=0.0, le=1.0)
    handoff_quality: float = Field(ge=0.0, le=1.0)
    consensus_alignment: float = Field(ge=0.0, le=1.0)
    conflict_resolution_readiness: float = Field(ge=0.0, le=1.0)
    shared_context_consistency: float = Field(ge=0.0, le=1.0)
    task_ownership_integrity: float = Field(ge=0.0, le=1.0)
    human_escalation_readiness: float = Field(ge=0.0, le=1.0)
    auditability_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    role_conflicts: int = Field(default=0, ge=0)
    unauthorized_delegations: int = Field(default=0, ge=0)
    failed_handoffs: int = Field(default=0, ge=0)
    unresolved_disagreements: int = Field(default=0, ge=0)
    coordination_deadlocks: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class MultiAgentCoordinationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[AgentCoordinationObservation] = Field(min_length=2)
    min_responsibility_clarity: float = Field(default=0.85, ge=0.0, le=1.0)
    min_delegation_integrity: float = Field(default=0.90, ge=0.0, le=1.0)
    min_consensus_alignment: float = Field(default=0.80, ge=0.0, le=1.0)
    min_handoff_quality: float = Field(default=0.85, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.35, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_agents(self):
        ids = [o.agent_id for o in self.observations]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate agent observation")
        return self


class AgentCoordinationDisposition(BaseModel):
    agent_id: str
    agent_version: str
    role: str
    assurance_score: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class MultiAgentCoordinationScores(BaseModel):
    role_clarity_assurance: float = Field(ge=0.0, le=1.0)
    delegation_assurance: float = Field(ge=0.0, le=1.0)
    handoff_assurance: float = Field(ge=0.0, le=1.0)
    consensus_assurance: float = Field(ge=0.0, le=1.0)
    context_consistency: float = Field(ge=0.0, le=1.0)
    escalation_readiness: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class MultiAgentCoordinationRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: MultiAgentCoordinationState
    scores: MultiAgentCoordinationScores
    dispositions: List[AgentCoordinationDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class MultiAgentCoordinationAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
