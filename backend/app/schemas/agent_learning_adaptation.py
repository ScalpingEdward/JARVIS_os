from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AgentLearningState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    ADAPTATION_READY = "adaptation-ready"
    EVIDENCE_GAP = "evidence-gap"
    OVERFIT_ALERT = "overfit-alert"
    REGRESSION_ALERT = "regression-alert"
    SAFETY_ALERT = "safety-alert"
    ROLLBACK_ALERT = "rollback-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class LearningObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    adaptation_id: str = Field(min_length=1, max_length=160)
    adaptation_type: str = Field(min_length=1, max_length=120)
    evidence_quality: float = Field(ge=0.0, le=1.0)
    outcome_support: float = Field(ge=0.0, le=1.0)
    causal_confidence: float = Field(ge=0.0, le=1.0)
    generalization_score: float = Field(ge=0.0, le=1.0)
    safety_validation_score: float = Field(ge=0.0, le=1.0)
    regression_test_coverage: float = Field(ge=0.0, le=1.0)
    rollback_readiness: float = Field(ge=0.0, le=1.0)
    human_review_coverage: float = Field(ge=0.0, le=1.0)
    provenance_coverage: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    failed_regressions: int = Field(default=0, ge=0)
    safety_failures: int = Field(default=0, ge=0)
    rollback_failures: int = Field(default=0, ge=0)
    overfit_indicators: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentLearningCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[LearningObservation] = Field(min_length=1)
    min_evidence_quality: float = Field(default=0.85, ge=0.0, le=1.0)
    min_generalization_score: float = Field(default=0.80, ge=0.0, le=1.0)
    min_safety_validation_score: float = Field(default=0.90, ge=0.0, le=1.0)
    min_rollback_readiness: float = Field(default=0.90, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.35, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_adaptations(self):
        keys = [(o.agent_id, o.adaptation_id) for o in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate agent/adaptation observation")
        return self


class LearningDisposition(BaseModel):
    agent_id: str
    adaptation_id: str
    assurance_score: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class AgentLearningScores(BaseModel):
    evidence_assurance: float = Field(ge=0.0, le=1.0)
    outcome_assurance: float = Field(ge=0.0, le=1.0)
    causal_assurance: float = Field(ge=0.0, le=1.0)
    generalization_assurance: float = Field(ge=0.0, le=1.0)
    safety_assurance: float = Field(ge=0.0, le=1.0)
    regression_assurance: float = Field(ge=0.0, le=1.0)
    rollback_assurance: float = Field(ge=0.0, le=1.0)
    governance_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentLearningRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AgentLearningState
    scores: AgentLearningScores
    dispositions: List[LearningDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class AgentLearningAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
