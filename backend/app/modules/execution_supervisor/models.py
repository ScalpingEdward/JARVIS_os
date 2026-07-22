from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class SupervisionState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    OBSERVING = "observing"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    INCIDENT = "incident"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    PAUSE_RECOMMENDED = "pause-recommended"
    ROLLBACK_RECOMMENDED = "rollback-recommended"
    RECOVERED = "recovered"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    FAILED = "failed"


class StageTelemetry(BaseModel):
    stage_key: str = Field(min_length=1, max_length=160)
    status: str = Field(min_length=1, max_length=80)
    progress_percent: float = Field(ge=0, le=100)
    elapsed_seconds: int = Field(ge=0)
    timeout_seconds: int = Field(gt=0)
    retry_count: int = Field(default=0, ge=0)
    retry_budget: int = Field(default=0, ge=0)
    error_rate: float = Field(default=0, ge=0, le=1)
    output_quality_score: float = Field(default=100, ge=0, le=100)
    dependency_healthy: bool = True
    heartbeat_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SupervisionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    workflow_id: str = Field(min_length=1, max_length=180)
    workflow_approved: bool
    v21_10_evidence: dict[str, Any] = Field(default_factory=dict)
    risk_brain_hard_block: bool = False
    stale_heartbeat_seconds: int = Field(default=300, ge=1, le=86400)
    minimum_quality_score: float = Field(default=70, ge=0, le=100)
    maximum_error_rate: float = Field(default=0.2, ge=0, le=1)
    stages: list[StageTelemetry] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_stage_keys(self) -> "SupervisionCreate":
        keys = [stage.stage_key for stage in self.stages]
        if len(keys) != len(set(keys)):
            raise ValueError("stage keys must be unique")
        return self


class IncidentSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Incident(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    stage_key: str
    code: str
    severity: IncidentSeverity
    message: str
    recommended_action: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SupervisionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    workflow_id: str
    state: SupervisionState
    health_score: float = 0
    delivery_drift_score: float = 0
    completed_stages: int = 0
    total_stages: int = 0
    incidents: list[Incident] = Field(default_factory=list)
    stage_snapshots: list[StageTelemetry] = Field(default_factory=list)
    decision_notes: list[str] = Field(default_factory=list)
    intervention_token: str | None = None
    downstream_receipt: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SupervisionCommand(str, Enum):
    REFRESH = "refresh"
    ACKNOWLEDGE = "acknowledge"
    RECOMMEND_PAUSE = "recommend-pause"
    RECOMMEND_ROLLBACK = "recommend-rollback"
    MARK_RECOVERED = "mark-recovered"
    COMPLETE = "complete"
    ARCHIVE = "archive"


class SupervisionAction(BaseModel):
    command: SupervisionCommand
    actor: str = Field(min_length=1, max_length=180)
    stages: list[StageTelemetry] | None = None
    intervention_token: str | None = None
    downstream_receipt: str | None = None
    reason: str | None = Field(default=None, max_length=4000)


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    record_id: str
    action: str
    actor: str
    from_state: str | None = None
    to_state: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
