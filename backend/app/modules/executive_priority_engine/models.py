from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PriorityState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    SCORING_PENDING = "scoring-pending"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    PRIORITIZED = "prioritized"
    APPROVED = "approved"
    ISSUED_TO_CAPACITY_PLANNING = "issued-to-capacity-planning"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    FAILED = "failed"


class StrategicObjectiveEvidence(BaseModel):
    objective_record_id: str = Field(min_length=1)
    objective_state: str = Field(min_length=1)
    approval_token: str = Field(min_length=8)
    objective: str = Field(min_length=1)
    success_metrics: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    business_value: float = Field(ge=0, le=100)
    urgency: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=100)
    estimated_effort: int = Field(ge=1)
    estimated_cost: float = Field(default=0, ge=0)
    risk_exposure: float = Field(default=0, ge=0, le=100)
    time_criticality: float = Field(default=0, ge=0, le=100)
    opportunity_enablement: float = Field(default=0, ge=0, le=100)
    human_approved: bool = False


class PriorityCandidate(BaseModel):
    candidate_key: str = Field(min_length=1)
    title: str = Field(min_length=1)
    impact_score: float = Field(ge=0, le=100)
    customer_value: float = Field(default=50, ge=0, le=100)
    strategic_alignment: float = Field(default=50, ge=0, le=100)
    urgency: float = Field(default=50, ge=0, le=100)
    confidence: float = Field(default=50, ge=0, le=100)
    risk_reduction: float = Field(default=0, ge=0, le=100)
    effort_points: int = Field(ge=1)
    estimated_cost: float = Field(default=0, ge=0)
    dependencies: list[str] = Field(default_factory=list)
    blocked: bool = False


class PriorityCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    v21_01_approved: bool = False
    upstream_risk_brain_blocked: bool = False
    evidence: StrategicObjectiveEvidence
    candidates: list[PriorityCandidate] = Field(min_length=1)
    dependency_status: dict[str, bool] = Field(default_factory=dict)


class RankedCandidate(BaseModel):
    candidate_key: str
    title: str
    rank: int = Field(ge=1)
    priority_score: float = Field(ge=0, le=100)
    cost_of_delay: float = Field(ge=0)
    wsjf_score: float = Field(ge=0)
    risk_adjusted_value: float = Field(ge=0)
    blocked: bool = False
    blocking_dependencies: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)


class PriorityRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: PriorityState
    detail: str
    request: PriorityCreate
    ranking: list[RankedCandidate] = Field(default_factory=list)
    portfolio_score: float = Field(default=0, ge=0, le=100)
    approval_token: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PriorityExecuteRequest(BaseModel):
    action: str
    actor_id: str = Field(min_length=1)
    human_approved: bool = False
    capacity_planning_receipt_id: str | None = None
    resolution_note: str | None = None


class PriorityAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: PriorityState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PriorityStatus(BaseModel):
    workspace_id: str
    total_records: int
    review_records: int
    prioritized_records: int
    approved_records: int
    issued_records: int
    blocked_records: int
