from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ImprovementPlanningState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    PLANNING = "planning"
    QUEUED = "queued"
    PRIORITIZED = "prioritized"
    SCHEDULED = "scheduled"
    READY_FOR_V20_01 = "ready-for-v20.01"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"
    FAILED = "failed"


class ApprovedImprovementEvidence(BaseModel):
    incident_learning_id: str = Field(min_length=1)
    incident_learning_state: str = Field(min_length=1)
    improvement_actions: list[str] = Field(default_factory=list)
    recurrence_risk_score: float = Field(default=0, ge=0, le=100)
    incident_severity: str = Field(default="medium", min_length=1)
    incident_count: int = Field(default=1, ge=1)
    estimated_outage_cost: float = Field(default=0, ge=0)
    requires_code_change: bool = False
    dependencies: list[str] = Field(default_factory=list)


class ImprovementPlanningCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    v20_08_improvement_approved: bool = False
    upstream_risk_brain_blocked: bool = False
    business_impact: int = Field(default=50, ge=0, le=100)
    technical_complexity: int = Field(default=50, ge=0, le=100)
    target_sprint: str | None = None
    evidence: ApprovedImprovementEvidence


class EngineeringBacklogItem(BaseModel):
    title: str
    description: str
    priority_score: float = Field(ge=0, le=100)
    effort_points: int = Field(ge=1, le=21)
    confidence_score: float = Field(ge=0, le=1)
    impact_score: float = Field(ge=0, le=100)
    defensive_only: bool = True
    duplicate_group_key: str
    dependencies: list[str] = Field(default_factory=list)


class ImprovementPlanningRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: ImprovementPlanningState
    detail: str
    request: ImprovementPlanningCreate
    backlog_items: list[EngineeringBacklogItem] = Field(default_factory=list)
    aggregate_priority_score: float = Field(default=0, ge=0, le=100)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ImprovementPlanningExecuteRequest(BaseModel):
    action: str
    actor_id: str = Field(min_length=1)
    target_sprint: str | None = None
    human_approved: bool = False


class ImprovementPlanningAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: ImprovementPlanningState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ImprovementPlanningStatus(BaseModel):
    workspace_id: str
    total_records: int
    queued_records: int
    prioritized_records: int
    ready_records: int
    blocked_records: int
