from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class OrchestrationStatus(str, Enum):
    draft = "draft"
    analyzed = "analyzed"
    pending_approval = "pending-approval"
    approved = "approved"
    rejected = "rejected"


class ApprovalDecision(str, Enum):
    approve = "approve"
    reject = "reject"


class MissionPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class MissionTaskInput(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    duration_hours: float = Field(gt=0, le=10000)
    required_capabilities: list[str] = Field(default_factory=list)
    dependency_keys: list[str] = Field(default_factory=list)
    candidate_agent_ids: list[str] = Field(default_factory=list)
    resource_units: float = Field(default=1.0, gt=0, le=1000)
    requires_human_approval: bool = True


class MissionInput(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=2000)
    priority: MissionPriority = MissionPriority.medium
    strategic_value: float = Field(default=50, ge=0, le=100)
    urgency: float = Field(default=50, ge=0, le=100)
    risk: float = Field(default=50, ge=0, le=100)
    tasks: list[MissionTaskInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_task_keys(self):
        keys = [task.key for task in self.tasks]
        if len(keys) != len(set(keys)):
            raise ValueError("Task keys must be unique within a mission")
        known = set(keys)
        for task in self.tasks:
            missing = set(task.dependency_keys) - known
            if missing:
                raise ValueError(f"Unknown task dependencies: {sorted(missing)}")
            if task.key in task.dependency_keys:
                raise ValueError("A task cannot depend on itself")
        return self


class AgentCapacity(BaseModel):
    agent_id: str = Field(min_length=1, max_length=100)
    capabilities: list[str] = Field(default_factory=list)
    available_hours: float = Field(default=0, ge=0, le=10000)
    reliability: float = Field(default=0.8, ge=0, le=1)
    current_load_hours: float = Field(default=0, ge=0, le=10000)


class OrchestrationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    owner_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    source_decision_ids: list[UUID] = Field(default_factory=list)
    missions: list[MissionInput] = Field(min_length=1)
    agents: list[AgentCapacity] = Field(default_factory=list)
    max_parallel_tasks: int = Field(default=3, ge=1, le=100)
    planning_horizon_hours: float = Field(default=168, gt=0, le=100000)

    @model_validator(mode="after")
    def validate_unique_keys(self):
        mission_keys = [mission.key for mission in self.missions]
        if len(mission_keys) != len(set(mission_keys)):
            raise ValueError("Mission keys must be unique")
        agent_ids = [agent.agent_id for agent in self.agents]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("Agent IDs must be unique")
        return self


class AgentAssignment(BaseModel):
    mission_key: str
    task_key: str
    assigned_agent_id: str | None
    fit_score: float
    explanation: list[str]


class ScheduledTask(BaseModel):
    mission_key: str
    task_key: str
    sequence: int
    start_hour: float
    end_hour: float
    dependency_keys: list[str]
    assigned_agent_id: str | None
    blocked_reasons: list[str]
    requires_human_approval: bool = True


class ResourceConflict(BaseModel):
    resource_key: str
    task_references: list[str]
    severity: str
    explanation: str


class MissionScore(BaseModel):
    mission_key: str
    priority_score: float
    strategic_value: float
    urgency: float
    risk_penalty: float
    readiness_score: float
    explanation: list[str]


class OrchestrationAnalysis(BaseModel):
    analyzed_at: datetime
    ranked_missions: list[MissionScore]
    task_schedule: list[ScheduledTask]
    assignments: list[AgentAssignment]
    conflicts: list[ResourceConflict]
    projected_duration_hours: float
    horizon_fit: bool
    utilization_by_agent: dict[str, float]
    deferred_tasks: list[str]
    recommendations: list[str]
    requires_human_approval: bool = True
    autonomous_execution_enabled: bool = False


class OrchestrationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    title: str
    source_decision_ids: list[UUID]
    missions: list[MissionInput]
    agents: list[AgentCapacity]
    max_parallel_tasks: int
    planning_horizon_hours: float
    status: OrchestrationStatus = OrchestrationStatus.draft
    analysis: OrchestrationAnalysis | None = None
    approved_by: str | None = None
    approval_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class ApprovalRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    reviewer_id: str = Field(min_length=1, max_length=100)
    decision: ApprovalDecision
    reason: str = Field(min_length=3, max_length=1000)


class OrchestrationStatusResponse(BaseModel):
    version: str = "17.1"
    orchestrations: int
    pending_approval: int
    approved: int
    rejected: int
    conflicts: int
    autonomous_execution_enabled: bool = False


class OrchestrationListResponse(BaseModel):
    items: list[OrchestrationRecord]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    orchestration_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
