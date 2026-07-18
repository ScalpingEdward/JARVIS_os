from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ExperienceType(str, Enum):
    MISSION = "mission"
    PLAN = "plan"
    PORTFOLIO = "portfolio"
    PLAYBOOK = "playbook"
    WORKFLOW = "workflow"
    AGENT = "agent"
    INCIDENT = "incident"
    STRATEGY = "strategy"


class OutcomeStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    CANCELLED = "cancelled"


class PatternKind(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PERFORMANCE = "performance"
    RISK = "risk"
    DRIFT = "drift"


class RecommendationState(str, Enum):
    PROPOSED = "proposed"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ImprovementState(str, Enum):
    OPEN = "open"
    ACCEPTED = "accepted"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    REJECTED = "rejected"


class MetricValue(BaseModel):
    key: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_.:-]+$")
    value: float
    unit: str = Field(default="", max_length=80)


class ExperienceCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    key: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_.:-]+$")
    experience_type: ExperienceType
    source_id: UUID | None = None
    title: str = Field(min_length=1, max_length=300)
    context: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list, max_length=100)
    expected_metrics: list[MetricValue] = Field(default_factory=list, max_length=100)
    knowledge_entity_ids: list[UUID] = Field(default_factory=list, max_length=200)
    human_approved: bool = True
    automatic_external_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "ExperienceCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_external_action:
            raise ValueError("automatic external actions are disabled")
        if len({item.key for item in self.expected_metrics}) != len(self.expected_metrics):
            raise ValueError("expected metric keys must be unique")
        return self


class ExperienceRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    key: str
    experience_type: ExperienceType
    source_id: UUID | None
    title: str
    context: dict[str, Any]
    tags: list[str]
    expected_metrics: list[MetricValue]
    knowledge_entity_ids: list[UUID]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OutcomeCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    actor_id: str = Field(min_length=1, max_length=120)
    experience_id: UUID
    status: OutcomeStatus
    actual_metrics: list[MetricValue] = Field(default_factory=list, max_length=100)
    root_causes: list[str] = Field(default_factory=list, max_length=100)
    lessons: list[str] = Field(default_factory=list, max_length=100)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    duration_minutes: int | None = Field(default=None, ge=0)
    cost: float | None = Field(default=None, ge=0)
    human_approved: bool = True
    automatic_external_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "OutcomeCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_external_action:
            raise ValueError("automatic external actions are disabled")
        if len({item.key for item in self.actual_metrics}) != len(self.actual_metrics):
            raise ValueError("actual metric keys must be unique")
        return self


class MetricDelta(BaseModel):
    key: str
    expected: float | None
    actual: float | None
    absolute_delta: float | None
    percentage_delta: float | None


class OutcomeRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    experience_id: UUID
    status: OutcomeStatus
    actual_metrics: list[MetricValue]
    metric_deltas: list[MetricDelta]
    root_causes: list[str]
    lessons: list[str]
    evidence_refs: list[str]
    confidence: float
    duration_minutes: int | None
    cost: float | None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PatternRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    kind: PatternKind
    key: str
    title: str
    description: str
    support_count: int = Field(ge=1)
    confidence: float = Field(ge=0.0, le=1.0)
    experience_ids: list[UUID]
    evidence: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DriftRecord(BaseModel):
    metric_key: str
    baseline_mean: float
    recent_mean: float
    absolute_change: float
    percentage_change: float | None
    severity: str = Field(pattern=r"^(info|warning|critical)$")
    sample_size: int = Field(ge=1)


class LearningRecommendation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    key: str
    title: str
    rationale: list[str]
    target_type: ExperienceType
    target_key: str | None = None
    expected_benefit: str
    confidence: float = Field(ge=0.0, le=1.0)
    pattern_ids: list[UUID] = Field(default_factory=list)
    state: RecommendationState = RecommendationState.PROPOSED
    automatic_application_enabled: bool = False
    reviewed_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RecommendationReview(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    reviewer_id: str = Field(min_length=1, max_length=120)
    approve: bool


class ImprovementRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    recommendation_id: UUID
    owner_id: str
    state: ImprovementState = ImprovementState.OPEN
    verification_metric: str = Field(default="", max_length=300)
    baseline_value: float | None = None
    observed_value: float | None = None
    notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ImprovementCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    recommendation_id: UUID
    verification_metric: str = Field(default="", max_length=300)
    baseline_value: float | None = None


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    target_type: str
    target_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LearningStatus(BaseModel):
    service: str = "continuous-learning"
    version: str = "16.0"
    experiences: int
    outcomes: int
    patterns: int
    recommendations: int
    open_improvements: int
    automatic_application_enabled: bool = False
    external_actions_enabled: bool = False
    human_approval_required: bool = True
    workspace_isolation: bool = True
