from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AgentResilienceImprovementState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    CONTROL_ALERT = "control-alert"
    RESILIENCE_ALERT = "resilience-alert"
    VALIDATION_ALERT = "validation-alert"
    REGRESSION_ALERT = "regression-alert"
    RECURRENCE_ALERT = "recurrence-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AgentResilienceImprovementObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    improvement_id: str = Field(min_length=1, max_length=160)
    control_implementation_score: float = Field(ge=0.0, le=1.0)
    resilience_test_coverage: float = Field(ge=0.0, le=1.0)
    chaos_test_readiness: float = Field(ge=0.0, le=1.0)
    failover_validation_score: float = Field(ge=0.0, le=1.0)
    recovery_validation_score: float = Field(ge=0.0, le=1.0)
    observability_validation_score: float = Field(ge=0.0, le=1.0)
    dependency_resilience_score: float = Field(ge=0.0, le=1.0)
    regression_coverage: float = Field(ge=0.0, le=1.0)
    owner_accountability: float = Field(ge=0.0, le=1.0)
    evidence_quality: float = Field(ge=0.0, le=1.0)
    recurrence_prevention_confidence: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    failed_resilience_tests: int = Field(default=0, ge=0)
    failed_failover_tests: int = Field(default=0, ge=0)
    failed_recovery_tests: int = Field(default=0, ge=0)
    regression_failures: int = Field(default=0, ge=0)
    repeat_incident_count: int = Field(default=0, ge=0)
    unresolved_control_gaps: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentResilienceImprovementCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[AgentResilienceImprovementObservation] = Field(min_length=1)
    min_control_implementation: float = Field(default=0.90, ge=0.0, le=1.0)
    min_resilience_validation: float = Field(default=0.90, ge=0.0, le=1.0)
    min_regression_coverage: float = Field(default=0.90, ge=0.0, le=1.0)
    min_recurrence_prevention: float = Field(default=0.90, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.30, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_improvements(self):
        keys = [(o.agent_id, o.improvement_id) for o in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate agent/improvement observation")
        return self


class AgentResilienceImprovementDisposition(BaseModel):
    agent_id: str
    agent_version: str
    improvement_id: str
    verification_score: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class AgentResilienceImprovementScores(BaseModel):
    control_assurance: float = Field(ge=0.0, le=1.0)
    resilience_assurance: float = Field(ge=0.0, le=1.0)
    failover_recovery_assurance: float = Field(ge=0.0, le=1.0)
    observability_assurance: float = Field(ge=0.0, le=1.0)
    dependency_assurance: float = Field(ge=0.0, le=1.0)
    regression_assurance: float = Field(ge=0.0, le=1.0)
    recurrence_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentResilienceImprovementRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AgentResilienceImprovementState
    scores: AgentResilienceImprovementScores
    dispositions: List[AgentResilienceImprovementDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class AgentResilienceImprovementAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
