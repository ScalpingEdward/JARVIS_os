from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ReviewDomain(str, Enum):
    mission = "mission"
    trading = "trading"
    agent = "agent"
    decision = "decision"
    system = "system"


class Outcome(str, Enum):
    success = "success"
    partial = "partial"
    failed = "failed"


class ExperimentMode(str, Enum):
    simulation = "simulation"
    backtest = "backtest"
    shadow = "shadow"
    ab_test = "ab_test"


class ReviewCreate(BaseModel):
    domain: ReviewDomain
    subject_id: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=1000)
    outcome: Outcome
    score: float = Field(ge=0, le=100)
    duration_seconds: float | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    metrics: dict[str, float] = Field(default_factory=dict)
    successes: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    tags: set[str] = Field(default_factory=set)


class ReviewRecord(ReviewCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ImprovementProposal(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    rationale: str
    expected_benefit: float = Field(ge=0, le=100)
    risk: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    supporting_review_ids: list[UUID] = Field(default_factory=list)
    requires_human_approval: bool = True
    approved: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExperimentCreate(BaseModel):
    proposal_id: UUID
    mode: ExperimentMode
    hypothesis: str = Field(min_length=1, max_length=1000)
    success_metrics: dict[str, float] = Field(default_factory=dict)
    max_runtime_seconds: int = Field(default=3600, ge=1, le=2592000)


class ExperimentRecord(ExperimentCreate):
    id: UUID = Field(default_factory=uuid4)
    status: str = "planned"
    result: dict[str, float | str | bool] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReflectionStatus(BaseModel):
    reviews: int
    proposals: int
    experiments: int
    approved_proposals: int
    automatic_self_modification: bool = False
    automatic_order_execution: bool = False
    automatic_merge: bool = False
