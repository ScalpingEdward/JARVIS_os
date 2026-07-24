from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AgentPostIncidentRecoveryState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    RESILIENT = "resilient"
    RECOVERY_GAP = "recovery-gap"
    CONTROL_GAP = "control-gap"
    RECURRENCE_ALERT = "recurrence-alert"
    VALIDATION_ALERT = "validation-alert"
    LESSONS_ALERT = "lessons-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AgentPostIncidentRecoveryObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    incident_id: str = Field(min_length=1, max_length=160)
    service_restoration_score: float = Field(ge=0.0, le=1.0)
    stability_validation_score: float = Field(ge=0.0, le=1.0)
    regression_validation_score: float = Field(ge=0.0, le=1.0)
    root_cause_confidence: float = Field(ge=0.0, le=1.0)
    corrective_action_coverage: float = Field(ge=0.0, le=1.0)
    preventive_control_coverage: float = Field(ge=0.0, le=1.0)
    resilience_test_coverage: float = Field(ge=0.0, le=1.0)
    observability_improvement_score: float = Field(ge=0.0, le=1.0)
    runbook_improvement_score: float = Field(ge=0.0, le=1.0)
    lessons_learned_closure: float = Field(ge=0.0, le=1.0)
    owner_accountability_coverage: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    open_corrective_actions: int = Field(default=0, ge=0)
    repeated_failure_signals: int = Field(default=0, ge=0)
    failed_resilience_tests: int = Field(default=0, ge=0)
    unresolved_root_cause_questions: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentPostIncidentRecoveryCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[AgentPostIncidentRecoveryObservation] = Field(min_length=1)
    min_restoration_score: float = Field(default=0.95, ge=0.0, le=1.0)
    min_stability_score: float = Field(default=0.90, ge=0.0, le=1.0)
    min_control_coverage: float = Field(default=0.90, ge=0.0, le=1.0)
    min_resilience_test_coverage: float = Field(default=0.90, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.25, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_agent_incident_pairs(self):
        pairs = [(o.agent_id, o.incident_id) for o in self.observations]
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate agent/incident recovery observation")
        return self


class AgentPostIncidentRecoveryDisposition(BaseModel):
    agent_id: str
    agent_version: str
    incident_id: str
    resilience_score: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class AgentPostIncidentRecoveryScores(BaseModel):
    restoration_assurance: float = Field(ge=0.0, le=1.0)
    validation_assurance: float = Field(ge=0.0, le=1.0)
    root_cause_assurance: float = Field(ge=0.0, le=1.0)
    corrective_control_assurance: float = Field(ge=0.0, le=1.0)
    resilience_assurance: float = Field(ge=0.0, le=1.0)
    observability_runbook_assurance: float = Field(ge=0.0, le=1.0)
    closure_accountability_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentPostIncidentRecoveryRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AgentPostIncidentRecoveryState
    scores: AgentPostIncidentRecoveryScores
    dispositions: List[AgentPostIncidentRecoveryDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class AgentPostIncidentRecoveryAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
