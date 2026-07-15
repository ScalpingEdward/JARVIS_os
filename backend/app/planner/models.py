from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class WorkerPreference(StrEnum):
    claude = "claude"
    openai = "openai"
    codex = "codex"
    cursor = "cursor"
    gemini = "gemini"
    any = "any"


class PlanStatus(StrEnum):
    draft = "draft"
    ready = "ready"
    active = "active"
    blocked = "blocked"
    completed = "completed"


class StepStatus(StrEnum):
    pending = "pending"
    ready = "ready"
    in_progress = "in_progress"
    review = "review"
    blocked = "blocked"
    completed = "completed"
    failed = "failed"


class PlanGoal(BaseModel):
    goal: str = Field(min_length=5, max_length=5000)
    context: str | None = Field(default=None, max_length=10000)
    constraints: list[str] = Field(default_factory=list, max_length=50)
    preferred_workers: list[WorkerPreference] = Field(default_factory=list)
    create_tasks: bool = False
    include_frontend: bool = True
    include_deployment: bool = True
    include_documentation: bool = True


class PlannedStep(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    sequence: int = Field(ge=1)
    phase: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    deliverables: list[str] = Field(default_factory=list, max_length=30)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=30)
    required_capabilities: list[str] = Field(default_factory=list)
    preferred_worker: WorkerPreference = WorkerPreference.any
    reviewer_worker: WorkerPreference | None = None
    priority: int = Field(default=50, ge=1, le=100)
    depends_on: list[UUID] = Field(default_factory=list)
    approval_required: bool = False
    approval_reason: str | None = None
    status: StepStatus = StepStatus.pending
    orchestrator_task_id: UUID | None = None


class ExecutionPlan(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    goal: str
    summary: str
    constraints: list[str] = Field(default_factory=list)
    status: PlanStatus = PlanStatus.draft
    steps: list[PlannedStep]
    created_task_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "ExecutionPlan":
        ids = {step.id for step in self.steps}
        sequences = [step.sequence for step in self.steps]
        if len(sequences) != len(set(sequences)):
            raise ValueError("Planning step sequences must be unique")
        for step in self.steps:
            if step.id in step.depends_on:
                raise ValueError("A planning step cannot depend on itself")
            if set(step.depends_on) - ids:
                raise ValueError("Planning step references an unknown dependency")
        return self


class PlanListResponse(BaseModel):
    items: list[ExecutionPlan]
    count: int


class PlanProgressResponse(BaseModel):
    plan_id: UUID
    status: PlanStatus
    total_steps: int
    completed_steps: int
    ready_steps: list[UUID]
    blocked_steps: list[UUID]
    progress_percent: int = Field(ge=0, le=100)


class StepStatusUpdate(BaseModel):
    status: StepStatus


class PlannerPreviewResponse(BaseModel):
    plan: ExecutionPlan
    tasks_created: bool
