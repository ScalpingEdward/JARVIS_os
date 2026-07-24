from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AgentProductionIncidentState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    CONTAINED = "contained"
    SEVERITY_ALERT = "severity-alert"
    CONTAINMENT_ALERT = "containment-alert"
    RECOVERY_ALERT = "recovery-alert"
    COMMUNICATION_ALERT = "communication-alert"
    POSTMORTEM_ALERT = "postmortem-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AgentProductionIncidentObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    incident_id: str = Field(min_length=1, max_length=160)
    severity: float = Field(ge=0.0, le=1.0)
    detection_quality: float = Field(ge=0.0, le=1.0)
    triage_readiness: float = Field(ge=0.0, le=1.0)
    containment_readiness: float = Field(ge=0.0, le=1.0)
    recovery_readiness: float = Field(ge=0.0, le=1.0)
    rollback_readiness: float = Field(ge=0.0, le=1.0)
    human_command_coverage: float = Field(ge=0.0, le=1.0)
    stakeholder_communication_readiness: float = Field(ge=0.0, le=1.0)
    evidence_preservation_score: float = Field(ge=0.0, le=1.0)
    postmortem_readiness: float = Field(ge=0.0, le=1.0)
    lessons_learned_traceability: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    unresolved_critical_impacts: int = Field(default=0, ge=0)
    containment_failures: int = Field(default=0, ge=0)
    recovery_failures: int = Field(default=0, ge=0)
    communication_failures: int = Field(default=0, ge=0)
    repeat_incident_count: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentProductionIncidentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[AgentProductionIncidentObservation] = Field(min_length=1)
    min_detection_quality: float = Field(default=0.85, ge=0.0, le=1.0)
    min_containment_readiness: float = Field(default=0.90, ge=0.0, le=1.0)
    min_recovery_readiness: float = Field(default=0.90, ge=0.0, le=1.0)
    min_human_command_coverage: float = Field(default=0.95, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.30, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_incidents(self):
        pairs = [(o.agent_id, o.incident_id) for o in self.observations]
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate agent/incident observation")
        return self


class AgentProductionIncidentDisposition(BaseModel):
    agent_id: str
    agent_version: str
    incident_id: str
    incident_assurance: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class AgentProductionIncidentScores(BaseModel):
    detection_assurance: float = Field(ge=0.0, le=1.0)
    containment_assurance: float = Field(ge=0.0, le=1.0)
    recovery_assurance: float = Field(ge=0.0, le=1.0)
    command_assurance: float = Field(ge=0.0, le=1.0)
    communication_assurance: float = Field(ge=0.0, le=1.0)
    evidence_assurance: float = Field(ge=0.0, le=1.0)
    learning_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentProductionIncidentRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AgentProductionIncidentState
    scores: AgentProductionIncidentScores
    dispositions: List[AgentProductionIncidentDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class AgentProductionIncidentAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
