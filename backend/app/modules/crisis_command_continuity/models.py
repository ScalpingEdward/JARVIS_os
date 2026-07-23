from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class CrisisState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    COMMAND_PLAN_READY = "command-plan-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVATED = "activated"
    STABILIZING = "stabilizing"
    RECOVERING = "recovering"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class IncidentSeverity(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    OPEN = "open"
    CONTAINED = "contained"
    RECOVERING = "recovering"
    RESOLVED = "resolved"


class CrisisIncident(BaseModel):
    incident_id: str = Field(min_length=1, max_length=180)
    domain: str = Field(min_length=1, max_length=180)
    owner: str = Field(min_length=1, max_length=180)
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.OPEN
    business_impact: float = Field(ge=0)
    maximum_tolerable_impact: float = Field(gt=0)
    recovery_time_objective_minutes: int = Field(gt=0)
    elapsed_minutes: int = Field(default=0, ge=0)
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContinuityAction(BaseModel):
    action_id: str = Field(min_length=1, max_length=180)
    title: str = Field(min_length=1, max_length=240)
    owner: str = Field(min_length=1, max_length=180)
    priority: int = Field(ge=1, le=100)
    confidence: float = Field(ge=0, le=1)
    reversible: bool = True
    evidence_refs: list[str] = Field(min_length=1)


class CrisisCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    enterprise_risk_record_id: str = Field(min_length=1, max_length=180)
    crisis_name: str = Field(min_length=1, max_length=240)
    incidents: list[CrisisIncident] = Field(min_length=1)
    continuity_actions: list[ContinuityAction] = Field(min_length=1)
    minimum_action_confidence: float = Field(default=0.9, ge=0, le=1)
    maximum_open_incidents: int = Field(default=0, ge=0)
    maximum_critical_incidents: int = Field(default=0, ge=0)
    maximum_aggregate_impact: float = Field(gt=0)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    crisis_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_records(self) -> "CrisisCreate":
        incident_ids = [item.incident_id for item in self.incidents]
        action_ids = [item.action_id for item in self.continuity_actions]
        if len(incident_ids) != len(set(incident_ids)):
            raise ValueError("incident_id values must be unique")
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("action_id values must be unique")
        return self


class CrisisActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|assess|prepare-command-plan|request-review|approve|activate|record-cycle|start-recovery|resolve|escalate|suspend|resume|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    cycle_healthy: bool | None = None
    observed_open_incidents: int | None = Field(default=None, ge=0)
    observed_critical_incidents: int | None = Field(default=None, ge=0)
    observed_aggregate_impact: float | None = Field(default=None, ge=0)
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: CrisisState | None = None
    to_state: CrisisState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class CrisisGovernanceRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    enterprise_risk_record_id: str
    crisis_name: str
    incidents: list[CrisisIncident]
    continuity_actions: list[ContinuityAction]
    minimum_action_confidence: float
    maximum_open_incidents: int
    maximum_critical_incidents: int
    maximum_aggregate_impact: float
    required_healthy_cycles: int
    crisis_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: CrisisState = CrisisState.DRAFT
    open_incidents: int = 0
    critical_incidents: int = 0
    aggregate_impact: float = 0
    approval_actor: str | None = None
    consecutive_healthy_cycles: int = 0
    command_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
