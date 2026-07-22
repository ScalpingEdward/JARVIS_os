from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class OrchestrationState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    INTAKE = "intake"
    DEPENDENCY_CHECK = "dependency-check"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    ORCHESTRATION_READY = "orchestration-ready"
    APPROVED = "approved"
    DISPATCHING = "dispatching"
    MONITORING = "monitoring"
    COMPLETED = "completed"
    PAUSED = "paused"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    FAILED = "failed"


class StageInput(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    module: str = Field(min_length=1, max_length=180)
    owner: str = Field(min_length=1, max_length=180)
    dependencies: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=900, ge=1, le=86400)
    max_retries: int = Field(default=2, ge=0, le=20)
    requires_human_gate: bool = False
    dispatch_enabled: bool = True
    rollback_action: str = Field(min_length=1, max_length=4000)
    expected_output: str = Field(min_length=1, max_length=2000)


class OrchestrationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    execution_plan_id: str = Field(min_length=1, max_length=180)
    execution_plan_approved: bool
    v21_09_evidence: dict[str, Any] = Field(default_factory=dict)
    risk_brain_hard_block: bool = False
    max_parallel_stages: int = Field(default=3, ge=1, le=100)
    deadlock_timeout_seconds: int = Field(default=1800, ge=30, le=86400)
    stages: list[StageInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_graph(self) -> "OrchestrationCreate":
        keys = [stage.key for stage in self.stages]
        if len(keys) != len(set(keys)):
            raise ValueError("stage keys must be unique")
        known = set(keys)
        for stage in self.stages:
            unknown = set(stage.dependencies) - known
            if unknown:
                raise ValueError(f"unknown dependencies for {stage.key}: {sorted(unknown)}")
            if stage.key in stage.dependencies:
                raise ValueError(f"stage {stage.key} cannot depend on itself")
        return self


class StageRuntime(BaseModel):
    key: str
    title: str
    module: str
    owner: str
    sequence: int
    lane: int
    dependencies: list[str]
    timeout_seconds: int
    max_retries: int
    retries_used: int = 0
    requires_human_gate: bool
    dispatch_enabled: bool
    rollback_action: str
    expected_output: str
    status: str = "pending"
    dispatch_token: str | None = None
    result_receipt: str | None = None
    last_error: str | None = None


class OrchestrationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    execution_plan_id: str
    state: OrchestrationState
    stages: list[StageRuntime] = Field(default_factory=list)
    ready_queue: list[str] = Field(default_factory=list)
    active_stages: list[str] = Field(default_factory=list)
    completed_stages: list[str] = Field(default_factory=list)
    failed_stages: list[str] = Field(default_factory=list)
    orchestration_readiness_score: float = 0
    delivery_confidence_score: float = 0
    approval_required: bool = True
    approval_token: str | None = None
    decision_notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OrchestrationCommand(str, Enum):
    APPROVE = "approve"
    DISPATCH = "dispatch"
    COMPLETE_STAGE = "complete-stage"
    FAIL_STAGE = "fail-stage"
    RETRY_STAGE = "retry-stage"
    PAUSE = "pause"
    RESUME = "resume"
    REJECT = "reject"
    ARCHIVE = "archive"


class OrchestrationAction(BaseModel):
    command: OrchestrationCommand
    actor: str = Field(min_length=1, max_length=180)
    stage_key: str | None = None
    approval_token: str | None = None
    dispatch_token: str | None = None
    result_receipt: str | None = None
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
