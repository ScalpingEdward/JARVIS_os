from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class IncidentLearningState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    ANALYSIS_PENDING = "analysis-pending"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    IMPROVEMENT_PROPOSED = "improvement-proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    FAILED = "failed"


class IncidentEvidence(BaseModel):
    incident_id: str = Field(min_length=1)
    incident_state: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    affected_components: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    remediation_actions: list[str] = Field(default_factory=list)
    recovery_verified: bool = False
    rollback_performed: bool = False
    duration_seconds: int = Field(default=0, ge=0)
    recurrence_count: int = Field(default=1, ge=1)


class IncidentLearningCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    v20_07_incident_closed: bool = False
    upstream_risk_brain_blocked: bool = False
    evidence: IncidentEvidence


class RootCauseFinding(BaseModel):
    category: str
    confidence: float = Field(ge=0, le=1)
    detail: str


class ResilienceImprovement(BaseModel):
    action: str
    defensive_only: bool = True
    requires_code_change: bool = False
    requires_human_review: bool = False


class IncidentLearningRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: IncidentLearningState
    detail: str
    request: IncidentLearningCreate
    root_causes: list[RootCauseFinding] = Field(default_factory=list)
    improvements: list[ResilienceImprovement] = Field(default_factory=list)
    recurrence_risk_score: float = Field(default=0, ge=0, le=100)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IncidentLearningExecuteRequest(BaseModel):
    action: str
    actor_id: str = Field(min_length=1)
    human_approved: bool = False


class IncidentLearningAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: IncidentLearningState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IncidentLearningStatus(BaseModel):
    workspace_id: str
    total_records: int
    proposed_records: int
    human_review_records: int
    blocked_records: int
