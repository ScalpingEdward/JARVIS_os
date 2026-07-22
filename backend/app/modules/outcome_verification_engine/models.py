from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class VerificationState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    INTAKE = "intake"
    VERIFYING = "verifying"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially-verified"
    NOT_VERIFIED = "not-verified"
    BENEFIT_AT_RISK = "benefit-at-risk"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    FAILED = "failed"


class OutcomeMetricInput(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    target_value: float
    actual_value: float
    tolerance_percent: float = Field(default=5.0, ge=0, le=100)
    weight: float = Field(default=1.0, gt=0, le=100)
    higher_is_better: bool = True
    evidence_refs: list[str] = Field(default_factory=list)
    mandatory: bool = True


class OutcomeVerificationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    workflow_id: str = Field(min_length=1, max_length=180)
    execution_supervisor_record_id: str = Field(min_length=1, max_length=180)
    v21_11_evidence: dict[str, Any] = Field(default_factory=dict)
    workflow_completed: bool
    risk_brain_hard_block: bool = False
    expected_benefit: float = Field(ge=0)
    realized_benefit: float = Field(ge=0)
    total_cost: float = Field(ge=0)
    planned_cost: float = Field(ge=0)
    metrics: list[OutcomeMetricInput] = Field(min_length=1)
    acceptance_threshold: float = Field(default=80.0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_metric_keys(self) -> "OutcomeVerificationCreate":
        keys = [metric.key for metric in self.metrics]
        if len(keys) != len(set(keys)):
            raise ValueError("metric keys must be unique")
        return self


class OutcomeMetricResult(BaseModel):
    key: str
    description: str
    target_value: float
    actual_value: float
    variance_percent: float
    attainment_percent: float
    weight: float
    passed: bool
    mandatory: bool
    evidence_refs: list[str]
    notes: list[str] = Field(default_factory=list)


class VerificationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    workflow_id: str
    execution_supervisor_record_id: str
    state: VerificationState
    metric_results: list[OutcomeMetricResult] = Field(default_factory=list)
    outcome_score: float = 0
    evidence_coverage_score: float = 0
    benefit_realization_percent: float = 0
    cost_variance_percent: float = 0
    value_for_money_score: float = 0
    mandatory_failures: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    acceptance_token: str | None = None
    downstream_receipt: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class VerificationCommand(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    REQUEST_REVIEW = "request-review"
    ISSUE = "issue"
    ARCHIVE = "archive"


class VerificationAction(BaseModel):
    command: VerificationCommand
    actor: str = Field(min_length=1, max_length=180)
    acceptance_token: str | None = None
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
