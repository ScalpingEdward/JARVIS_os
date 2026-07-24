from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AgentOutcomeVerificationState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    OUTCOME_DRIFT = "outcome-drift"
    FEEDBACK_GAP = "feedback-gap"
    KPI_ALERT = "kpi-alert"
    REGRESSION_ALERT = "regression-alert"
    LEARNING_ALERT = "learning-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AgentOutcomeObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    decision_id: str = Field(min_length=1, max_length=200)
    objective_id: str = Field(min_length=1, max_length=200)
    expected_outcome_score: float = Field(ge=0.0, le=1.0)
    observed_outcome_score: float = Field(ge=0.0, le=1.0)
    kpi_attainment_score: float = Field(ge=0.0, le=1.0)
    evidence_quality_score: float = Field(ge=0.0, le=1.0)
    feedback_coverage_score: float = Field(ge=0.0, le=1.0)
    causal_attribution_score: float = Field(ge=0.0, le=1.0)
    regression_detection_score: float = Field(ge=0.0, le=1.0)
    learning_traceability_score: float = Field(ge=0.0, le=1.0)
    rollback_readiness_score: float = Field(ge=0.0, le=1.0)
    human_review_coverage: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    adverse_outcomes: int = Field(default=0, ge=0)
    missed_kpis: int = Field(default=0, ge=0)
    repeated_regressions: int = Field(default=0, ge=0)
    unreviewed_feedback_items: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentOutcomeVerificationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[AgentOutcomeObservation] = Field(min_length=1)
    min_kpi_attainment: float = Field(default=0.80, ge=0.0, le=1.0)
    min_feedback_coverage: float = Field(default=0.85, ge=0.0, le=1.0)
    min_evidence_quality: float = Field(default=0.85, ge=0.0, le=1.0)
    max_outcome_gap: float = Field(default=0.20, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.35, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_decisions(self):
        keys = [(o.agent_id, o.decision_id) for o in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate agent/decision observation")
        return self


class AgentOutcomeDisposition(BaseModel):
    agent_id: str
    decision_id: str
    assurance_score: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class AgentOutcomeVerificationScores(BaseModel):
    outcome_fidelity: float = Field(ge=0.0, le=1.0)
    kpi_assurance: float = Field(ge=0.0, le=1.0)
    evidence_assurance: float = Field(ge=0.0, le=1.0)
    feedback_assurance: float = Field(ge=0.0, le=1.0)
    causal_assurance: float = Field(ge=0.0, le=1.0)
    regression_assurance: float = Field(ge=0.0, le=1.0)
    learning_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentOutcomeVerificationRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AgentOutcomeVerificationState
    scores: AgentOutcomeVerificationScores
    dispositions: List[AgentOutcomeDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class AgentOutcomeVerificationAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
