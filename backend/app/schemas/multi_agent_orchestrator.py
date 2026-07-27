from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class OrchestrationState(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    DISPATCH_READY = "dispatch-ready"
    RUNNING = "running"
    WAITING = "waiting"
    HANDOFF_REQUIRED = "handoff-required"
    VALIDATION_REQUIRED = "validation-required"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class OrchestratorTask(BaseModel):
    task_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    required_capabilities: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    required_data_domains: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)
    assigned_agent_id: Optional[str] = None
    human_approval_required: bool = False
    validator_required: bool = True
    max_attempts: int = Field(default=2, ge=1, le=10)
    timeout_seconds: int = Field(default=900, ge=30, le=86400)


class AgentBinding(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    capabilities: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    data_domains: List[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    active: bool = True
    max_parallel_tasks: int = Field(default=1, ge=1, le=100)
    human_owner: Optional[str] = None


class OrchestrationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    planner_record_id: str = Field(min_length=1, max_length=160)
    goal: str = Field(min_length=1, max_length=1000)
    tasks: List[OrchestratorTask] = Field(min_length=1)
    agents: List[AgentBinding] = Field(min_length=1)
    max_parallel_tasks: int = Field(default=4, ge=1, le=100)
    min_agent_confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_graph(self):
        task_ids = [t.task_id for t in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("duplicate task_id")
        known = set(task_ids)
        for task in self.tasks:
            unknown = set(task.depends_on) - known
            if unknown:
                raise ValueError(f"unknown task dependency: {sorted(unknown)}")
            if task.task_id in task.depends_on:
                raise ValueError("task cannot depend on itself")
        agent_ids = [a.agent_id for a in self.agents]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("duplicate agent_id")
        return self


class TaskAssignment(BaseModel):
    task_id: str
    agent_id: Optional[str]
    eligible: bool
    readiness_score: float = Field(ge=0.0, le=1.0)
    blockers: List[str] = Field(default_factory=list)
    status: str = "pending"
    attempts: int = 0
    validator_status: str = "not-started"


class OrchestrationScores(BaseModel):
    assignment_coverage: float = Field(ge=0.0, le=1.0)
    dependency_readiness: float = Field(ge=0.0, le=1.0)
    capability_coverage: float = Field(ge=0.0, le=1.0)
    validation_coverage: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)


class OrchestrationRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    planner_record_id: str
    goal: str
    state: OrchestrationState
    assignments: List[TaskAssignment]
    scores: OrchestrationScores
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class OrchestrationAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    task_id: Optional[str] = None
    reason: Optional[str] = None
