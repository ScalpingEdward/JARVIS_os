from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class TaskPlanState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    PLANNED = "planned"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    READY = "ready"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class PlannerGoal(BaseModel):
    goal_id: str = Field(min_length=1, max_length=160)
    objective: str = Field(min_length=3, max_length=4000)
    required_capabilities: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    required_data_domains: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(min_length=1)
    max_tasks: int = Field(default=12, ge=1, le=100)
    max_parallel_tasks: int = Field(default=3, ge=1, le=20)
    max_total_budget: float = Field(default=100.0, ge=0.0)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence_floor: float = Field(default=0.75, ge=0.0, le=1.0)


class PlannedTask(BaseModel):
    task_id: str
    title: str
    description: str
    required_capabilities: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    required_data_domains: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)
    assigned_agent_id: Optional[str] = None
    estimated_budget: float = Field(default=0.0, ge=0.0)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    human_approval_required: bool = False
    execution_allowed: bool = False


class TaskPlanCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    goal: PlannerGoal
    tasks: List[PlannedTask] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_graph(self):
        if len(self.tasks) > self.goal.max_tasks:
            raise ValueError("task count exceeds goal max_tasks")
        ids = [task.task_id for task in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate task_id")
        known = set(ids)
        for task in self.tasks:
            if task.task_id in task.depends_on:
                raise ValueError("task cannot depend on itself")
            if not set(task.depends_on).issubset(known):
                raise ValueError("task dependency references unknown task")
        return self


class TaskPlanScores(BaseModel):
    dependency_integrity: float = Field(ge=0.0, le=1.0)
    capability_coverage: float = Field(ge=0.0, le=1.0)
    budget_fit: float = Field(ge=0.0, le=1.0)
    parallelism_fit: float = Field(ge=0.0, le=1.0)
    plan_assurance: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)


class TaskPlanRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: TaskPlanState
    goal: PlannerGoal
    tasks: List[PlannedTask]
    scores: TaskPlanScores
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class TaskPlanAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
