from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ExecutionRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReadinessState(str, Enum):
    READY = "ready"
    CONDITIONAL = "conditional"
    BLOCKED = "blocked"


class RecommendationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ExecutionTask(BaseModel):
    key: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_.:-]+$")
    title: str = Field(min_length=1, max_length=300)
    duration_minutes: int = Field(gt=0, le=525_600)
    dependencies: list[str] = Field(default_factory=list, max_length=100)
    required_capabilities: dict[str, float] = Field(default_factory=dict)
    earliest_start_offset_minutes: int = Field(default=0, ge=0)
    success_probability: float = Field(default=0.8, ge=0.0, le=1.0)
    risk: ExecutionRisk = ExecutionRisk.MEDIUM
    human_approval_gate: bool = False


class CapacityWindow(BaseModel):
    capability: str = Field(min_length=1, max_length=160)
    available_units: float = Field(ge=0)
    window_start_offset_minutes: int = Field(default=0, ge=0)
    window_end_offset_minutes: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_window(self) -> "CapacityWindow":
        if self.window_end_offset_minutes <= self.window_start_offset_minutes:
            raise ValueError("capacity window end must be after start")
        return self


class ExecutionAnalysisCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    key: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_.:-]+$")
    title: str = Field(min_length=1, max_length=300)
    plan_id: UUID | None = None
    portfolio_id: UUID | None = None
    tasks: list[ExecutionTask] = Field(min_length=1, max_length=500)
    capacity_windows: list[CapacityWindow] = Field(default_factory=list, max_length=500)
    target_completion_minutes: int | None = Field(default=None, gt=0)
    baseline_version: str | None = Field(default=None, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_execution: bool = False

    @model_validator(mode="after")
    def validate_analysis(self) -> "ExecutionAnalysisCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_execution:
            raise ValueError("automatic execution is disabled")
        keys = {task.key for task in self.tasks}
        if len(keys) != len(self.tasks):
            raise ValueError("task keys must be unique")
        for task in self.tasks:
            if task.key in task.dependencies:
                raise ValueError("task cannot depend on itself")
            if any(dependency not in keys for dependency in task.dependencies):
                raise ValueError("task dependency must reference an existing task")
        return self


class ScheduledTask(BaseModel):
    task_key: str
    start_offset_minutes: int
    end_offset_minutes: int
    slack_minutes: int
    critical: bool
    readiness: ReadinessState
    blocking_reasons: list[str] = Field(default_factory=list)


class BottleneckRecord(BaseModel):
    capability: str
    required_units: float
    available_units: float
    deficit_units: float
    affected_task_keys: list[str]
    severity: RecommendationSeverity


class CapacityForecastPoint(BaseModel):
    capability: str
    offset_minutes: int
    required_units: float
    available_units: float
    utilization: float


class ExecutiveRecommendation(BaseModel):
    severity: RecommendationSeverity
    action: str
    reason: str
    task_keys: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionAnalysisRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    key: str
    title: str
    plan_id: UUID | None
    portfolio_id: UUID | None
    baseline_version: str | None
    scheduled_tasks: list[ScheduledTask]
    critical_path: list[str]
    total_duration_minutes: int
    readiness_score: float = Field(ge=0.0, le=1.0)
    readiness_state: ReadinessState
    success_probability: float = Field(ge=0.0, le=1.0)
    execution_risk: ExecutionRisk
    bottlenecks: list[BottleneckRecord]
    capacity_forecast: list[CapacityForecastPoint]
    recommendations: list[ExecutiveRecommendation]
    decision_delta: dict[str, Any] = Field(default_factory=dict)
    external_execution_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StrategicExecutionStatus(BaseModel):
    service: str = "strategic-execution-intelligence"
    version: str = "15.3"
    analyses: int
    ready_analyses: int
    blocked_analyses: int
    open_bottlenecks: int
    autonomous_execution_enabled: bool = False
    external_actions_enabled: bool = False
    human_approval_required: bool = True
    workspace_isolation: bool = True


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    target_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
