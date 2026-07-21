from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RoadmapState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    GENERATING = "generating"
    SCHEDULE_CONFLICT = "schedule-conflict"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    ROADMAP_READY = "roadmap-ready"
    APPROVED = "approved"
    ISSUED_TO_KPI = "issued-to-kpi"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    FAILED = "failed"


class FundedWorkstream(BaseModel):
    workstream_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    priority_rank: int = Field(ge=1)
    effort_points: int = Field(ge=1)
    allocated_budget: float = Field(ge=0)
    expected_value: float = Field(ge=0)
    dependencies: list[str] = Field(default_factory=list)
    dependency_ready: bool = True
    owner_role: str = Field(min_length=1)
    target_start: date | None = None
    target_end: date | None = None


class RoadmapCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    v21_04_budget_approved: bool = False
    upstream_risk_brain_blocked: bool = False
    budget_approval_token: str = Field(min_length=8)
    planning_horizon_days: int = Field(default=90, ge=7, le=730)
    max_parallel_workstreams: int = Field(default=3, ge=1, le=50)
    strategic_constraints: list[str] = Field(default_factory=list)
    workstreams: list[FundedWorkstream] = Field(default_factory=list)


class RoadmapMilestone(BaseModel):
    milestone_id: str
    title: str
    sequence: int = Field(ge=1)
    owner_role: str
    start_date: date
    end_date: date
    workstream_ids: list[str] = Field(default_factory=list)
    allocated_budget: float = Field(ge=0)
    expected_value: float = Field(ge=0)
    dependencies: list[str] = Field(default_factory=list)
    exit_criteria: list[str] = Field(default_factory=list)


class RoadmapRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: RoadmapState
    detail: str
    request: RoadmapCreate
    milestones: list[RoadmapMilestone] = Field(default_factory=list)
    total_budget: float = Field(default=0, ge=0)
    total_expected_value: float = Field(default=0, ge=0)
    roadmap_confidence: float = Field(default=0, ge=0, le=100)
    approval_token: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RoadmapExecuteRequest(BaseModel):
    action: str
    actor_id: str = Field(min_length=1)
    human_approved: bool = False
    kpi_receipt_id: str | None = None
    resolution_note: str | None = None


class RoadmapAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: RoadmapState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RoadmapStatus(BaseModel):
    workspace_id: str
    total_records: int
    ready_records: int
    approved_records: int
    issued_records: int
    conflict_records: int
    blocked_records: int
