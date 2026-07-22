from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ReliabilityState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    DRAFT = "draft"
    SCORED = "scored"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    OPTIMIZATION_QUEUED = "optimization-queued"
    APPLIED = "applied"
    VERIFIED = "verified"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ReliabilityBand(str, Enum):
    CRITICAL = "critical"
    WEAK = "weak"
    STABLE = "stable"
    STRONG = "strong"
    EXCELLENT = "excellent"


class ControlMetric(BaseModel):
    metric_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    weight: float = Field(gt=0, le=1)
    observed_value: float
    target_value: float
    higher_is_better: bool = True
    evidence_refs: list[str] = Field(default_factory=list)


class OptimizationProposal(BaseModel):
    proposal_id: str = Field(min_length=1, max_length=100)
    control_name: str = Field(min_length=1, max_length=200)
    current_value: str = Field(min_length=1, max_length=500)
    proposed_value: str = Field(min_length=1, max_length=500)
    expected_impact: str = Field(min_length=1, max_length=1000)
    requires_restart: bool = False


class ReliabilityCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=200)
    review_record_id: str = Field(min_length=1, max_length=100)
    system_name: str = Field(min_length=1, max_length=200)
    metrics: list[ControlMetric] = Field(min_length=1)
    proposals: list[OptimizationProposal] = Field(default_factory=list)
    upstream_evidence_verified: bool = False
    risk_brain_blocked: bool = False

    @model_validator(mode="after")
    def validate_unique_ids_and_weights(self) -> "ReliabilityCreate":
        metric_ids = [item.metric_id for item in self.metrics]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("duplicate reliability metric")
        proposal_ids = [item.proposal_id for item in self.proposals]
        if len(proposal_ids) != len(set(proposal_ids)):
            raise ValueError("duplicate optimization proposal")
        total_weight = sum(item.weight for item in self.metrics)
        if abs(total_weight - 1.0) > 0.0001:
            raise ValueError("reliability metric weights must total 1.0")
        return self


class ReliabilityAction(BaseModel):
    action: Literal["score", "request-review", "approve", "queue-optimization", "apply", "verify", "reject", "archive"]
    actor_id: str = Field(min_length=1, max_length=100)
    approval_token: str | None = Field(default=None, min_length=8, max_length=500)
    receipt_id: str | None = Field(default=None, min_length=1, max_length=200)
    applied_proposal_ids: list[str] = Field(default_factory=list)
    verification_passed: bool | None = None
    reason: str | None = Field(default=None, max_length=2000)


class ReliabilityRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    review_record_id: str
    system_name: str
    metrics: list[ControlMetric]
    proposals: list[OptimizationProposal]
    state: ReliabilityState
    score: float = 0
    band: ReliabilityBand = ReliabilityBand.CRITICAL
    risk_brain_blocked: bool
    upstream_evidence_verified: bool
    approval_token_hash: str | None = None
    applied_proposal_ids: list[str] = Field(default_factory=list)
    last_receipt_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditEvent(BaseModel):
    event_id: str
    record_id: str
    workspace_id: str
    action: str
    actor_id: str
    state: ReliabilityState
    reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
