from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class MissionState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ALIGNED = "aligned"
    EXECUTIVE_REVIEW_REQUIRED = "executive-review-required"
    APPROVED = "approved"
    ACTIVATED = "activated"
    EXECUTING = "executing"
    MONITORING = "monitoring"
    ACHIEVED = "achieved"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    ABORTED = "aborted"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class MissionPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MissionObjective(BaseModel):
    objective_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    target_metric: str = Field(min_length=1, max_length=240)
    target_value: float | int | str | bool
    tolerance: float | None = Field(default=None, ge=0)
    deadline: datetime | None = None
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StrategicMissionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    governance_record_id: str = Field(min_length=1, max_length=180)
    mission_name: str = Field(min_length=1, max_length=240)
    priority: MissionPriority
    objectives: list[MissionObjective] = Field(min_length=1)
    strategic_evidence_refs: list[str] = Field(min_length=1)
    maximum_execution_cycles: int = Field(default=20, ge=1, le=10000)
    required_success_cycles: int = Field(default=3, ge=1, le=100)
    aggregate_risk: float = Field(default=0, ge=0, le=1)
    maximum_aggregate_risk: float = Field(default=0.7, ge=0, le=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_objectives(self) -> "StrategicMissionCreate":
        ids = [item.objective_id for item in self.objectives]
        if len(ids) != len(set(ids)):
            raise ValueError("objective_id values must be unique")
        return self


class MissionActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|align|request-review|approve|activate|start|record-cycle|achieve|escalate|suspend|resume|abort|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    cycle_successful: bool | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    aggregate_risk: float | None = Field(default=None, ge=0, le=1)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: MissionState | None = None
    to_state: MissionState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class StrategicMission(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    governance_record_id: str
    mission_name: str
    priority: MissionPriority
    objectives: list[MissionObjective]
    strategic_evidence_refs: list[str]
    maximum_execution_cycles: int
    required_success_cycles: int
    aggregate_risk: float
    maximum_aggregate_risk: float
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: MissionState = MissionState.DRAFT
    approval_actor: str | None = None
    execution_cycles: int = 0
    consecutive_success_cycles: int = 0
    execution_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
