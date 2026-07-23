from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class ExecutiveState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ANALYZED = "analyzed"
    DECISION_READY = "decision-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVATED = "activated"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class ObjectiveStatus(str, Enum):
    ON_TRACK = "on-track"
    AT_RISK = "at-risk"
    BREACHED = "breached"
    ACHIEVED = "achieved"


class StrategicObjective(BaseModel):
    objective_id: str = Field(min_length=1, max_length=180)
    title: str = Field(min_length=1, max_length=240)
    owner: str = Field(min_length=1, max_length=180)
    weight: float = Field(gt=0, le=1)
    current_score: float = Field(ge=0, le=1)
    minimum_acceptable_score: float = Field(ge=0, le=1)
    status: ObjectiveStatus = ObjectiveStatus.ON_TRACK
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutiveOption(BaseModel):
    option_id: str = Field(min_length=1, max_length=180)
    title: str = Field(min_length=1, max_length=240)
    owner: str = Field(min_length=1, max_length=180)
    expected_business_impact: float = Field(ge=-1, le=1)
    expected_risk_impact: float = Field(ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)
    reversible: bool = True
    evidence_refs: list[str] = Field(min_length=1)


class ExecutiveDecisionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    maturity_record_id: str = Field(min_length=1, max_length=180)
    decision_name: str = Field(min_length=1, max_length=240)
    objectives: list[StrategicObjective] = Field(min_length=1)
    options: list[ExecutiveOption] = Field(min_length=2)
    selected_option_id: str = Field(min_length=1, max_length=180)
    minimum_option_confidence: float = Field(default=0.85, ge=0, le=1)
    minimum_weighted_objective_score: float = Field(default=0.7, ge=0, le=1)
    maximum_breached_objectives: int = Field(default=0, ge=0)
    maximum_at_risk_objectives: int = Field(default=1, ge=0)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    decision_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_records(self) -> "ExecutiveDecisionCreate":
        objective_ids = [item.objective_id for item in self.objectives]
        option_ids = [item.option_id for item in self.options]
        if len(objective_ids) != len(set(objective_ids)):
            raise ValueError("objective_id values must be unique")
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("option_id values must be unique")
        if self.selected_option_id not in set(option_ids):
            raise ValueError("selected_option_id must reference a known option")
        total_weight = sum(item.weight for item in self.objectives)
        if abs(total_weight - 1.0) > 0.0001:
            raise ValueError("objective weights must sum to 1")
        return self


class ExecutiveActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|analyze|prepare-decision|request-review|approve|activate|record-cycle|verify|escalate|suspend|resume|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    cycle_healthy: bool | None = None
    observed_weighted_objective_score: float | None = Field(default=None, ge=0, le=1)
    observed_breached_objectives: int | None = Field(default=None, ge=0)
    observed_at_risk_objectives: int | None = Field(default=None, ge=0)
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: ExecutiveState | None = None
    to_state: ExecutiveState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class ExecutiveDecisionRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    maturity_record_id: str
    decision_name: str
    objectives: list[StrategicObjective]
    options: list[ExecutiveOption]
    selected_option_id: str
    minimum_option_confidence: float
    minimum_weighted_objective_score: float
    maximum_breached_objectives: int
    maximum_at_risk_objectives: int
    required_healthy_cycles: int
    decision_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: ExecutiveState = ExecutiveState.DRAFT
    weighted_objective_score: float = 0
    breached_objectives: int = 0
    at_risk_objectives: int = 0
    selected_option_score: float = 0
    approval_actor: str | None = None
    consecutive_healthy_cycles: int = 0
    activation_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
