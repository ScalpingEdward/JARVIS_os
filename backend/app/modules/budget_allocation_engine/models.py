from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class BudgetAllocationState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    ALLOCATION_PENDING = "allocation-pending"
    BUDGET_CONSTRAINED = "budget-constrained"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    PLAN_READY = "plan-ready"
    APPROVED = "approved"
    ISSUED_TO_ROADMAP = "issued-to-roadmap"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    FAILED = "failed"


class CapacityAllocationEvidence(BaseModel):
    capacity_record_id: str = Field(min_length=1)
    capacity_state: str = Field(min_length=1)
    approval_token: str = Field(min_length=8)
    total_effort_points: float = Field(gt=0)
    allocated_effort_points: float = Field(ge=0)
    estimated_labor_cost: float = Field(ge=0)
    estimated_ai_cost: float = Field(ge=0)
    estimated_cloud_cost: float = Field(ge=0)
    workstream_ids: list[str] = Field(default_factory=list)
    dependency_blocked_workstreams: list[str] = Field(default_factory=list)
    human_approved: bool = False


class BudgetEnvelope(BaseModel):
    total_budget: float = Field(gt=0)
    labor_budget: float = Field(ge=0)
    ai_budget: float = Field(ge=0)
    cloud_budget: float = Field(ge=0)
    contingency_budget: float = Field(ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    reserve_ratio: float = Field(default=0.10, ge=0, le=0.50)
    hard_cost_ceiling: float | None = Field(default=None, gt=0)


class BudgetAllocationCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    v21_03_capacity_approved: bool = False
    upstream_risk_brain_blocked: bool = False
    evidence: CapacityAllocationEvidence
    envelope: BudgetEnvelope
    strategic_priority_score: float = Field(default=50, ge=0, le=100)
    expected_business_value: float = Field(default=0, ge=0)
    target_period: str = Field(min_length=1)


class BudgetLine(BaseModel):
    category: str
    requested_amount: float = Field(ge=0)
    allocated_amount: float = Field(ge=0)
    variance_amount: float
    utilization_ratio: float = Field(ge=0)
    rationale: str


class BudgetAllocationPlan(BaseModel):
    currency: str
    target_period: str
    total_requested: float = Field(ge=0)
    total_allocated: float = Field(ge=0)
    contingency_reserved: float = Field(ge=0)
    unallocated_budget: float
    projected_roi: float | None = None
    affordability_score: float = Field(ge=0, le=100)
    lines: list[BudgetLine] = Field(default_factory=list)
    blocked_workstreams: list[str] = Field(default_factory=list)
    execution_boundary: str = "planning-only"


class BudgetAllocationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: BudgetAllocationState
    detail: str
    request: BudgetAllocationCreate
    plan: BudgetAllocationPlan | None = None
    approval_token: str | None = None
    roadmap_receipt_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BudgetAllocationExecuteRequest(BaseModel):
    action: str
    actor_id: str = Field(min_length=1)
    human_approved: bool = False
    roadmap_receipt_id: str | None = None
    resolution_note: str | None = None


class BudgetAllocationAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: BudgetAllocationState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BudgetAllocationStatus(BaseModel):
    workspace_id: str
    total_records: int
    ready_records: int
    constrained_records: int
    approved_records: int
    issued_records: int
    blocked_records: int
