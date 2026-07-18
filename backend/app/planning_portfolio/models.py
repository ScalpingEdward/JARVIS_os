from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PortfolioState(str, Enum):
    DRAFT = "draft"
    ANALYZED = "analyzed"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    ARCHIVED = "archived"


class ConflictSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class CapacityProfile(BaseModel):
    capability: str = Field(min_length=1, max_length=160)
    available_units: float = Field(gt=0, le=100_000)
    planning_window_minutes: int = Field(gt=0, le=525_600)


class PortfolioCandidate(BaseModel):
    plan_id: UUID
    selected_option_key: str = Field(min_length=1, max_length=120)
    strategic_value: float = Field(default=0.5, ge=0, le=1)
    urgency: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)
    estimated_cost: float = Field(default=0, ge=0)
    estimated_duration_minutes: int = Field(default=0, ge=0)
    required_capacity: dict[str, float] = Field(default_factory=dict)
    dependencies: list[UUID] = Field(default_factory=list, max_length=100)
    affected_entity_ids: list[UUID] = Field(default_factory=list, max_length=200)


class PortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    key: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_.:-]+$")
    title: str = Field(min_length=1, max_length=300)
    candidates: list[PortfolioCandidate] = Field(min_length=2, max_length=100)
    capacity_profiles: list[CapacityProfile] = Field(default_factory=list, max_length=100)
    max_total_cost: float | None = Field(default=None, ge=0)
    max_parallel_plans: int = Field(default=3, ge=1, le=100)
    human_approved: bool = True
    automatic_external_action: bool = False

    @model_validator(mode="after")
    def validate_safety(self) -> "PortfolioCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_external_action:
            raise ValueError("automatic external actions are disabled")
        if len({item.plan_id for item in self.candidates}) != len(self.candidates):
            raise ValueError("portfolio plan IDs must be unique")
        if len({item.capability for item in self.capacity_profiles}) != len(self.capacity_profiles):
            raise ValueError("capacity capabilities must be unique")
        candidate_ids = {item.plan_id for item in self.candidates}
        for candidate in self.candidates:
            if candidate.plan_id in candidate.dependencies:
                raise ValueError("a plan cannot depend on itself")
            if any(item not in candidate_ids for item in candidate.dependencies):
                raise ValueError("portfolio dependencies must reference portfolio candidates")
        return self


class PortfolioRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    key: str
    title: str
    candidates: list[PortfolioCandidate]
    capacity_profiles: list[CapacityProfile]
    max_total_cost: float | None
    max_parallel_plans: int
    state: PortfolioState = PortfolioState.DRAFT
    approved_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PortfolioAnalysisRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    actor_id: str = Field(min_length=1, max_length=120)
    strategic_weight: float = Field(default=0.35, ge=0, le=1)
    urgency_weight: float = Field(default=0.25, ge=0, le=1)
    confidence_weight: float = Field(default=0.20, ge=0, le=1)
    efficiency_weight: float = Field(default=0.20, ge=0, le=1)

    @model_validator(mode="after")
    def validate_weights(self) -> "PortfolioAnalysisRequest":
        total = self.strategic_weight + self.urgency_weight + self.confidence_weight + self.efficiency_weight
        if abs(total - 1.0) > 0.0001:
            raise ValueError("portfolio analysis weights must sum to 1.0")
        return self


class CandidateScore(BaseModel):
    plan_id: UUID
    score: float
    rank: int
    blocked_by: list[UUID]
    capacity_fit: bool
    cost_fit: bool
    reasons: list[str]


class ResourceConflict(BaseModel):
    capability: str
    required_units: float
    available_units: float
    deficit_units: float
    plan_ids: list[UUID]
    severity: ConflictSeverity


class ReplanningAction(BaseModel):
    action: str
    plan_id: UUID | None = None
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PortfolioAnalysisRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    portfolio_id: UUID
    scores: list[CandidateScore]
    recommended_sequence: list[UUID]
    deferred_plan_ids: list[UUID]
    conflicts: list[ResourceConflict]
    replanning_actions: list[ReplanningAction]
    total_selected_cost: float
    stable: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    reviewer_id: str = Field(min_length=1, max_length=120)


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    target_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PortfolioStatus(BaseModel):
    service: str = "planning-portfolio"
    version: str = "15.2"
    portfolios: int
    analyses: int
    approved_portfolios: int
    open_conflicts: int
    adaptive_replanning_enabled: bool = True
    autonomous_execution_enabled: bool = False
    human_approval_required: bool = True
    workspace_isolation: bool = True
