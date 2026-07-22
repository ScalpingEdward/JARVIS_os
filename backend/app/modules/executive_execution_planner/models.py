from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class ExecutionPlanState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    PLANNING = "planning"
    DEPENDENCY_VALIDATION = "dependency-validation"
    CAPACITY_VALIDATION = "capacity-validation"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    EXECUTION_PLAN_READY = "execution-plan-ready"
    APPROVED = "approved"
    ISSUED_TO_ORCHESTRATOR = "issued-to-orchestrator"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    FAILED = "failed"


class WorkPackageInput(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    owner: str = Field(min_length=1, max_length=160)
    effort_points: int = Field(ge=1, le=10000)
    duration_days: int = Field(ge=1, le=3650)
    expected_value: float = Field(ge=0)
    allocated_budget: float = Field(ge=0)
    dependencies: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    exit_criteria: list[str] = Field(default_factory=list)
    rollback_plan: str = Field(min_length=1, max_length=4000)
    dependency_ready: bool = True


class ExecutionPlanCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    investment_decision_id: str = Field(min_length=1, max_length=180)
    investment_decision_approved: bool
    v21_08_evidence: dict[str, Any] = Field(default_factory=dict)
    risk_brain_hard_block: bool = False
    strategic_constraints: list[str] = Field(default_factory=list)
    available_capacity_points: int = Field(ge=1)
    planning_horizon_days: int = Field(ge=1, le=3650)
    max_parallel_workstreams: int = Field(default=3, ge=1, le=100)
    work_packages: list[WorkPackageInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_keys(self) -> "ExecutionPlanCreate":
        keys = [item.key for item in self.work_packages]
        if len(keys) != len(set(keys)):
            raise ValueError("work package keys must be unique")
        known = set(keys)
        for item in self.work_packages:
            unknown = set(item.dependencies) - known
            if unknown:
                raise ValueError(f"unknown dependencies for {item.key}: {sorted(unknown)}")
            if item.key in item.dependencies:
                raise ValueError(f"work package {item.key} cannot depend on itself")
        return self


class WorkPackagePlan(BaseModel):
    key: str
    title: str
    owner: str
    sequence: int
    lane: int
    start_day: int
    end_day: int
    effort_points: int
    duration_days: int
    expected_value: float
    allocated_budget: float
    dependencies: list[str]
    deliverables: list[str]
    exit_criteria: list[str]
    rollback_plan: str
    is_critical_path: bool = False


class ExecutionPlanRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    investment_decision_id: str
    state: ExecutionPlanState
    work_packages: list[WorkPackagePlan] = Field(default_factory=list)
    critical_path: list[str] = Field(default_factory=list)
    bottlenecks: list[str] = Field(default_factory=list)
    total_effort_points: int = 0
    total_budget: float = 0
    total_expected_value: float = 0
    execution_readiness_score: float = 0
    delivery_confidence_score: float = 0
    approval_required: bool = True
    approval_token: str | None = None
    downstream_receipt: str | None = None
    decision_notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ExecutionCommand(str, Enum):
    GENERATE = "generate"
    APPROVE = "approve"
    ISSUE = "issue"
    REJECT = "reject"
    ARCHIVE = "archive"


class ExecutionPlanAction(BaseModel):
    command: ExecutionCommand
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = None
    downstream_receipt: str | None = None
    reason: str | None = Field(default=None, max_length=4000)


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    record_id: str
    action: str
    actor: str
    from_state: str | None = None
    to_state: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
