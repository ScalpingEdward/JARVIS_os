from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class GoalDomain(str, Enum):
    trading = "trading"
    business = "business"
    engineering = "engineering"
    finance = "finance"
    health = "health"
    legal = "legal"
    personal = "personal"


class GoalStatus(str, Enum):
    planned = "planned"
    active = "active"
    blocked = "blocked"
    completed = "completed"
    paused = "paused"


class Milestone(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=2, max_length=160)
    completed: bool = False
    weight: int = Field(default=1, ge=1, le=100)


class StrategicGoalCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    domain: GoalDomain
    priority: int = Field(default=50, ge=1, le=100)
    target_date: datetime | None = None
    milestones: list[Milestone] = Field(default_factory=list)
    dependencies: list[UUID] = Field(default_factory=list)
    notes: str = Field(default="", max_length=2000)


class StrategicGoal(StrategicGoalCreate):
    id: UUID = Field(default_factory=uuid4)
    owner_name: str = "MASTER Brano"
    status: GoalStatus = GoalStatus.planned
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    automatic_execution: bool = False


class ProgressUpdate(BaseModel):
    progress: float = Field(ge=0.0, le=1.0)
    status: GoalStatus | None = None
    note: str = Field(default="", max_length=1000)


class StrategicPlan(BaseModel):
    owner_name: str = "MASTER Brano"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    goals: list[StrategicGoal]
    top_priorities: list[UUID]
    conflicts: list[str]
    blockers: list[str]
    recommendations: list[str]
    requires_human_approval: bool = True
    automatic_execution: bool = False


class StrategicPlanningStatus(BaseModel):
    owner_name: str = "MASTER Brano"
    goals: int
    active: int
    blocked: int
    completed: int
    automatic_execution: bool = False
    automatic_order_execution: bool = False
