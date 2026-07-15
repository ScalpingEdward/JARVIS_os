from datetime import date, datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class RoadmapPriority(StrEnum):
    critical = "critical"
    high = "high"
    normal = "normal"
    low = "low"


class RoadmapStatus(StrEnum):
    planned = "planned"
    active = "active"
    blocked = "blocked"
    completed = "completed"


class WorkStatus(StrEnum):
    pending = "pending"
    ready = "ready"
    in_progress = "in_progress"
    blocked = "blocked"
    completed = "completed"


class RoadmapCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    goal: str = Field(min_length=5, max_length=5000)
    target_date: date | None = None
    priority: RoadmapPriority = RoadmapPriority.normal
    constraints: list[str] = Field(default_factory=list, max_length=50)
    preferred_agents: list[str] = Field(default_factory=list, max_length=10)


class RoadmapTask(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str
    milestone_id: UUID
    status: WorkStatus = WorkStatus.pending
    priority: RoadmapPriority = RoadmapPriority.normal
    assigned_agent: str
    reviewer_agent: str
    depends_on: list[UUID] = Field(default_factory=list)
    estimated_hours: int = Field(default=4, ge=1, le=40)
    due_date: date | None = None
    blocker: str | None = None
    approval_required: bool = False


class RoadmapMilestone(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    objective: str
    sequence: int = Field(ge=1)
    status: WorkStatus = WorkStatus.pending
    due_date: date | None = None
    depends_on: list[UUID] = Field(default_factory=list)
    task_ids: list[UUID] = Field(default_factory=list)


class AuditEntry(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action: str
    details: str


class RoadmapRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    goal: str
    target_date: date | None = None
    priority: RoadmapPriority
    status: RoadmapStatus = RoadmapStatus.planned
    constraints: list[str] = Field(default_factory=list)
    milestones: list[RoadmapMilestone]
    tasks: list[RoadmapTask]
    audit_log: list[AuditEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_graph(self) -> "RoadmapRecord":
        task_ids = {task.id for task in self.tasks}
        milestone_ids = {milestone.id for milestone in self.milestones}
        for task in self.tasks:
            if task.milestone_id not in milestone_ids:
                raise ValueError("Task references unknown milestone")
            if set(task.depends_on) - task_ids:
                raise ValueError("Task references unknown dependency")
            if task.id in task.depends_on:
                raise ValueError("Task cannot depend on itself")
        for milestone in self.milestones:
            if set(milestone.depends_on) - milestone_ids:
                raise ValueError("Milestone references unknown dependency")
        return self


class TaskStatusUpdate(BaseModel):
    status: WorkStatus
    blocker: str | None = Field(default=None, max_length=1000)


class RoadmapProgress(BaseModel):
    roadmap_id: UUID
    status: RoadmapStatus
    progress_percent: int
    completed_tasks: int
    total_tasks: int
    completed_milestones: int
    total_milestones: int


class TodayPlan(BaseModel):
    roadmap_id: UUID
    generated_for: date
    task_ids: list[UUID]
    estimated_hours: int


class RiskItem(BaseModel):
    level: RoadmapPriority
    code: str
    message: str
    task_id: UUID | None = None
    milestone_id: UUID | None = None


class RiskReport(BaseModel):
    roadmap_id: UUID
    risks: list[RiskItem]
    count: int


class ReplanResponse(BaseModel):
    roadmap: RoadmapRecord
    changed_task_ids: list[UUID]
