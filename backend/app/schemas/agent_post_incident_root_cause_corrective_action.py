from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AgentPostIncidentRcaState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    ROOT_CAUSE_ALERT = "root-cause-alert"
    CORRECTIVE_ACTION_ALERT = "corrective-action-alert"
    PREVENTIVE_ACTION_ALERT = "preventive-action-alert"
    OWNER_ALERT = "owner-alert"
    RECURRENCE_ALERT = "recurrence-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AgentPostIncidentRcaObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    incident_id: str = Field(min_length=1, max_length=160)
    root_cause_confidence: float = Field(ge=0.0, le=1.0)
    evidence_completeness: float = Field(ge=0.0, le=1.0)
    causal_chain_coverage: float = Field(ge=0.0, le=1.0)
    contributing_factor_coverage: float = Field(ge=0.0, le=1.0)
    corrective_action_quality: float = Field(ge=0.0, le=1.0)
    preventive_action_quality: float = Field(ge=0.0, le=1.0)
    owner_accountability: float = Field(ge=0.0, le=1.0)
    due_date_readiness: float = Field(ge=0.0, le=1.0)
    verification_plan_quality: float = Field(ge=0.0, le=1.0)
    recurrence_prevention_score: float = Field(ge=0.0, le=1.0)
    cross_agent_impact_review: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    unresolved_root_causes: int = Field(default=0, ge=0)
    overdue_corrective_actions: int = Field(default=0, ge=0)
    failed_verification_checks: int = Field(default=0, ge=0)
    repeat_incident_count: int = Field(default=0, ge=0)
    unowned_actions: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentPostIncidentRcaCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[AgentPostIncidentRcaObservation] = Field(min_length=1)
    min_root_cause_confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    min_corrective_action_quality: float = Field(default=0.90, ge=0.0, le=1.0)
    min_preventive_action_quality: float = Field(default=0.85, ge=0.0, le=1.0)
    min_owner_accountability: float = Field(default=0.95, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.30, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_incidents(self):
        pairs = [(o.agent_id, o.incident_id) for o in self.observations]
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate agent/incident observation")
        return self


class AgentPostIncidentRcaDisposition(BaseModel):
    agent_id: str
    agent_version: str
    incident_id: str
    assurance_score: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class AgentPostIncidentRcaScores(BaseModel):
    root_cause_assurance: float = Field(ge=0.0, le=1.0)
    evidence_assurance: float = Field(ge=0.0, le=1.0)
    corrective_action_assurance: float = Field(ge=0.0, le=1.0)
    preventive_action_assurance: float = Field(ge=0.0, le=1.0)
    accountability_assurance: float = Field(ge=0.0, le=1.0)
    verification_assurance: float = Field(ge=0.0, le=1.0)
    recurrence_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentPostIncidentRcaRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AgentPostIncidentRcaState
    scores: AgentPostIncidentRcaScores
    dispositions: List[AgentPostIncidentRcaDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class AgentPostIncidentRcaAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
