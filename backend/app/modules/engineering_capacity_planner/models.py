from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CapacityPlanningState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    PLANNING = "planning"
    CAPACITY_CONSTRAINED = "capacity-constrained"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    PLAN_READY = "plan-ready"
    APPROVED = "approved"
    ISSUED_TO_BUDGET_PLANNING = "issued-to-budget-planning"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    FAILED = "failed"


class PrioritizedWorkItem(BaseModel):
    candidate_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    rank: int = Field(ge=1)
    priority_score: float = Field(ge=0, le=100)
    effort_points: int = Field(ge=1)
    required_roles: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    dependency_ready: bool = True
    target_window: str | None = None


class CapacityResource(BaseModel):
    resource_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    role: str = Field(min_length=1)
    skills: list[str] = Field(default_factory=list)
    available_points: int = Field(ge=0)
    max_parallel_items: int = Field(default=1, ge=1)
    hourly_cost: float = Field(default=0, ge=0)
    available: bool = True


class CapacityPlanningCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    v21_02_priority_approved: bool = False
    upstream_risk_brain_blocked: bool = False
    planning_horizon: str = Field(min_length=1)
    max_total_cost: float | None = Field(default=None, ge=0)
    work_items: list[PrioritizedWorkItem] = Field(default_factory=list)
    resources: list[CapacityResource] = Field(default_factory=list)


class CapacityAllocation(BaseModel):
    candidate_id: str
    assigned_resource_ids: list[str] = Field(default_factory=list)
    allocated_points: int = Field(ge=0)
    estimated_cost: float = Field(ge=0)
    status: str
    reason: str


class CapacityPlanningRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: CapacityPlanningState
    detail: str
    request: CapacityPlanningCreate
    allocations: list[CapacityAllocation] = Field(default_factory=list)
    total_available_points: int = Field(default=0, ge=0)
    total_required_points: int = Field(default=0, ge=0)
    utilization_percent: float = Field(default=0, ge=0, le=100)
    estimated_total_cost: float = Field(default=0, ge=0)
    unallocated_candidate_ids: list[str] = Field(default_factory=list)
    approval_token: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CapacityPlanningExecuteRequest(BaseModel):
    action: str
    actor_id: str = Field(min_length=1)
    human_approved: bool = False
    budget_planning_receipt_id: str | None = None


class CapacityPlanningAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: CapacityPlanningState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CapacityPlanningStatus(BaseModel):
    workspace_id: str
    total_records: int
    ready_records: int
    constrained_records: int
    approved_records: int
    issued_records: int
    blocked_records: int
