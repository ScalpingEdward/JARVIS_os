from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class RecoveryState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    DRAFT = "draft"
    PLANNED = "planned"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    QUEUED = "queued"
    EXECUTING = "executing"
    VERIFIED = "verified"
    REJECTED = "rejected"
    FAILED = "failed"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class RecoveryStrategy(str, Enum):
    ROLLBACK = "rollback"
    RECONFIGURE = "reconfigure"
    RESTART = "restart"
    ISOLATE = "isolation"
    OBSERVE = "observe"
    MANUAL_ESCALATION = "manual-escalation"


class RecoveryStep(BaseModel):
    step_id: str = Field(min_length=1, max_length=120)
    strategy: RecoveryStrategy
    title: str = Field(min_length=1, max_length=180)
    target: str = Field(min_length=1, max_length=240)
    priority: int = Field(ge=1, le=100)
    depends_on: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(min_length=1)
    failure_criteria: list[str] = Field(default_factory=list)
    max_attempts: int = Field(default=1, ge=1, le=10)
    cooldown_seconds: int = Field(default=0, ge=0, le=86400)
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecoveryPlanCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    assurance_assessment_id: str = Field(min_length=1, max_length=180)
    trust_assessment_id: str = Field(min_length=1, max_length=180)
    rollback_assessment_id: str | None = Field(default=None, max_length=180)
    incident_id: str | None = Field(default=None, max_length=180)
    steps: list[RecoveryStep] = Field(min_length=1)
    assurance_evidence_refs: list[str] = Field(min_length=1)
    runtime_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_plan(self) -> "RecoveryPlanCreate":
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("step_id values must be unique")
        known = set(step_ids)
        for step in self.steps:
            if step.step_id in step.depends_on:
                raise ValueError("recovery step cannot depend on itself")
            missing = set(step.depends_on) - known
            if missing:
                raise ValueError("all dependencies must reference known recovery steps")
        graph = {step.step_id: set(step.depends_on) for step in self.steps}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("recovery step dependencies must be acyclic")
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph[node]:
                visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)
        return self


class RecoveryActionRequest(BaseModel):
    action: str = Field(pattern="^(plan|request-review|approve|queue|start|complete-step|verify|reject|fail|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    step_id: str | None = Field(default=None, max_length=120)
    attempt: int | None = Field(default=None, ge=1, le=10)
    execution_evidence_refs: list[str] = Field(default_factory=list)
    verification_evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class StepExecution(BaseModel):
    step_id: str
    attempts: int = 0
    completed: bool = False
    receipt_ids: list[str] = Field(default_factory=list)
    execution_evidence_refs: list[str] = Field(default_factory=list)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: RecoveryState | None = None
    to_state: RecoveryState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class RecoveryPlan(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    assurance_assessment_id: str
    trust_assessment_id: str
    rollback_assessment_id: str | None = None
    incident_id: str | None = None
    steps: list[RecoveryStep]
    assurance_evidence_refs: list[str]
    runtime_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: RecoveryState = RecoveryState.DRAFT
    execution: dict[str, StepExecution] = Field(default_factory=dict)
    approval_actor: str | None = None
    verification_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
