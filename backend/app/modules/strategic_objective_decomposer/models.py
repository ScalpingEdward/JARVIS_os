from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class StrategicObjectiveState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    DECOMPOSITION_PENDING = "decomposition-pending"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    ISSUED_TO_EXECUTIVE_PLANNING = "issued-to-executive-planning"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    FAILED = "failed"


class StrategicObjectiveCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    objective: str = Field(min_length=8)
    target_date: str | None = None
    business_value: int = Field(default=50, ge=0, le=100)
    urgency: int = Field(default=50, ge=0, le=100)
    confidence: int = Field(default=50, ge=0, le=100)
    budget_limit: float | None = Field(default=None, ge=0)
    constraints: list[str] = Field(default_factory=list)
    known_dependencies: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    upstream_risk_brain_blocked: bool = False


class StrategicDeliverable(BaseModel):
    id: str
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    estimated_effort_points: int = Field(ge=1, le=21)
    priority_score: float = Field(ge=0, le=100)
    owner_role: str


class StrategicMilestone(BaseModel):
    id: str
    title: str
    objective: str
    deliverable_ids: list[str] = Field(default_factory=list)
    exit_criteria: list[str] = Field(default_factory=list)
    sequence: int = Field(ge=1)


class StrategicObjectivePlan(BaseModel):
    objective: str
    executive_summary: str
    milestones: list[StrategicMilestone] = Field(default_factory=list)
    deliverables: list[StrategicDeliverable] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    total_effort_points: int = Field(default=0, ge=0)
    aggregate_priority_score: float = Field(default=0, ge=0, le=100)
    planning_boundary: str = "executive-planning-only"


class StrategicObjectiveRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: StrategicObjectiveState
    detail: str
    request: StrategicObjectiveCreate
    plan: StrategicObjectivePlan | None = None
    approval_token: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StrategicObjectiveExecuteRequest(BaseModel):
    action: str
    actor_id: str = Field(min_length=1)
    human_approved: bool = False
    resolution_note: str | None = None


class StrategicObjectiveAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: StrategicObjectiveState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StrategicObjectiveStatus(BaseModel):
    workspace_id: str
    total_records: int
    review_records: int
    approved_records: int
    issued_records: int
    blocked_records: int
