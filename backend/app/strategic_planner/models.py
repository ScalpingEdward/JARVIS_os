from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PlanDomain(str, Enum):
    trading = "trading"
    business = "business"
    engineering = "engineering"
    personal = "personal"
    investment = "investment"
    operations = "operations"


class PlanState(str, Enum):
    draft = "draft"
    active = "active"
    at_risk = "at_risk"
    blocked = "blocked"
    completed = "completed"
    archived = "archived"


class MilestoneState(str, Enum):
    planned = "planned"
    ready = "ready"
    active = "active"
    blocked = "blocked"
    completed = "completed"


class ResourceNeed(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    amount: float = Field(default=1, ge=0)
    unit: str = Field(default="unit", min_length=1, max_length=40)
    available: float = Field(default=0, ge=0)


class StrategicRisk(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    probability: float = Field(ge=0, le=1)
    impact: float = Field(ge=0, le=1)
    mitigation: str = Field(min_length=1, max_length=1000)


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=2000)
    priority: int = Field(default=3, ge=1, le=5)
    target_date: date | None = None
    dependencies: list[str] = Field(default_factory=list)
    resources: list[ResourceNeed] = Field(default_factory=list)
    success_metrics: dict[str, float] = Field(default_factory=dict)


class StrategicPlanCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    objective: str = Field(min_length=1, max_length=3000)
    domain: PlanDomain
    horizon_months: int = Field(default=12, ge=1, le=120)
    priority: int = Field(default=3, ge=1, le=5)
    target_date: date | None = None
    constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    milestones: list[MilestoneCreate] = Field(default_factory=list)
    risks: list[StrategicRisk] = Field(default_factory=list)


class MilestoneRecord(MilestoneCreate):
    id: UUID = Field(default_factory=uuid4)
    state: MilestoneState = MilestoneState.planned
    progress: float = Field(default=0, ge=0, le=1)
    blocker: str | None = None


class StrategicPlanRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    objective: str
    domain: PlanDomain
    horizon_months: int
    priority: int
    target_date: date | None
    constraints: list[str]
    assumptions: list[str]
    milestones: list[MilestoneRecord]
    risks: list[StrategicRisk]
    state: PlanState = PlanState.draft
    progress: float = Field(default=0, ge=0, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)
    recommended_focus: list[UUID] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MilestoneUpdate(BaseModel):
    state: MilestoneState | None = None
    progress: float | None = Field(default=None, ge=0, le=1)
    blocker: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def completed_requires_full_progress(self):
        if self.state == MilestoneState.completed and self.progress not in {None, 1}:
            raise ValueError("Completed milestones require progress=1")
        return self


class PlanActivation(BaseModel):
    approved_by: str = Field(min_length=1, max_length=120)


class PlanListResponse(BaseModel):
    items: list[StrategicPlanRecord]
    count: int


class StrategicPlannerStatus(BaseModel):
    total_plans: int
    active: int
    at_risk: int
    blocked: int
    completed: int
    average_progress: float
    automatic_execution: bool = False
    automatic_order_execution: bool = False
    automatic_merge: bool = False
