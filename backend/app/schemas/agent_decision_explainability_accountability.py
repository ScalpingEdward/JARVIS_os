from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AgentDecisionAccountabilityState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    EXPLAINABLE = "explainable"
    RATIONALE_GAP = "rationale-gap"
    EVIDENCE_GAP = "evidence-gap"
    TRACEABILITY_ALERT = "traceability-alert"
    ACCOUNTABILITY_ALERT = "accountability-alert"
    OVERRIDE_ALERT = "override-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AgentDecisionObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    decision_id: str = Field(min_length=1, max_length=160)
    decision_type: str = Field(min_length=1, max_length=120)
    rationale_completeness: float = Field(ge=0.0, le=1.0)
    evidence_coverage: float = Field(ge=0.0, le=1.0)
    source_traceability: float = Field(ge=0.0, le=1.0)
    counterfactual_quality: float = Field(ge=0.0, le=1.0)
    uncertainty_disclosure: float = Field(ge=0.0, le=1.0)
    policy_reference_coverage: float = Field(ge=0.0, le=1.0)
    human_owner_coverage: float = Field(ge=0.0, le=1.0)
    reviewability_score: float = Field(ge=0.0, le=1.0)
    override_traceability: float = Field(ge=0.0, le=1.0)
    reproducibility_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    missing_evidence_count: int = Field(default=0, ge=0)
    untraceable_sources: int = Field(default=0, ge=0)
    undocumented_overrides: int = Field(default=0, ge=0)
    unresolved_challenges: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentDecisionAccountabilityCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[AgentDecisionObservation] = Field(min_length=1)
    min_rationale_completeness: float = Field(default=0.85, ge=0.0, le=1.0)
    min_evidence_coverage: float = Field(default=0.85, ge=0.0, le=1.0)
    min_traceability: float = Field(default=0.90, ge=0.0, le=1.0)
    min_human_owner_coverage: float = Field(default=0.95, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.35, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_decisions(self):
        pairs = [(o.agent_id, o.decision_id) for o in self.observations]
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate agent/decision observation")
        return self


class AgentDecisionDisposition(BaseModel):
    agent_id: str
    decision_id: str
    assurance_score: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class AgentDecisionAccountabilityScores(BaseModel):
    rationale_assurance: float = Field(ge=0.0, le=1.0)
    evidence_assurance: float = Field(ge=0.0, le=1.0)
    traceability_assurance: float = Field(ge=0.0, le=1.0)
    uncertainty_assurance: float = Field(ge=0.0, le=1.0)
    policy_accountability: float = Field(ge=0.0, le=1.0)
    human_accountability: float = Field(ge=0.0, le=1.0)
    reviewability_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentDecisionAccountabilityRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AgentDecisionAccountabilityState
    scores: AgentDecisionAccountabilityScores
    dispositions: List[AgentDecisionDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class AgentDecisionAccountabilityAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
