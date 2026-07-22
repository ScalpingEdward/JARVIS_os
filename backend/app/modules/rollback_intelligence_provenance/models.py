from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class RollbackState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    DRAFT = "draft"
    ANALYZED = "analyzed"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    ROLLBACK_QUEUED = "rollback-queued"
    ROLLBACK_EXECUTED = "rollback-executed"
    VERIFIED = "verified"
    REJECTED = "rejected"
    FAILED = "failed"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class RollbackRecommendation(str, Enum):
    KEEP_CURRENT = "keep-current"
    ROLLBACK = "rollback"
    HOLD_FOR_REVIEW = "hold-for-review"


class ProvenanceNode(BaseModel):
    version: str = Field(min_length=1, max_length=160)
    artifact_digest: str = Field(min_length=8, max_length=256)
    parent_version: str | None = Field(default=None, max_length=160)
    deployed_at: datetime
    source_ref: str = Field(min_length=1, max_length=300)
    runtime_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RollbackSignal(BaseModel):
    signal_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=180)
    baseline: float
    observed: float
    weight: float = Field(gt=0, le=1)
    deterioration_direction: str = Field(pattern="^(higher|lower)$")
    critical: bool = False
    evidence_ref: str = Field(min_length=1, max_length=300)

    def normalized_deterioration(self) -> float:
        denominator = max(abs(self.baseline), 1e-9)
        if self.deterioration_direction == "higher":
            delta = (self.observed - self.baseline) / denominator
        else:
            delta = (self.baseline - self.observed) / denominator
        return max(0.0, min(1.0, delta))


class RollbackAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    deployment_verification_id: str = Field(min_length=1, max_length=180)
    current: ProvenanceNode
    rollback_target: ProvenanceNode
    signals: list[RollbackSignal] = Field(min_length=1)
    deployment_evidence_refs: list[str] = Field(min_length=1)
    runtime_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_integrity(self) -> "RollbackAssessmentCreate":
        signal_ids = [signal.signal_id for signal in self.signals]
        if len(signal_ids) != len(set(signal_ids)):
            raise ValueError("signal_id values must be unique")
        total_weight = sum(signal.weight for signal in self.signals)
        if abs(total_weight - 1.0) > 1e-6:
            raise ValueError("signal weights must total exactly 1.0")
        if self.current.version == self.rollback_target.version:
            raise ValueError("rollback target must differ from current version")
        return self


class RollbackActionRequest(BaseModel):
    action: str = Field(
        pattern="^(analyze|request-review|approve|queue-rollback|execute-rollback|verify|reject|fail|archive)$"
    )
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    verification_evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: RollbackState | None = None
    to_state: RollbackState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class RollbackAssessment(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    deployment_verification_id: str
    current: ProvenanceNode
    rollback_target: ProvenanceNode
    signals: list[RollbackSignal]
    deployment_evidence_refs: list[str]
    runtime_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: RollbackState = RollbackState.DRAFT
    deterioration_score: float = 0.0
    critical_signal_count: int = 0
    recommendation: RollbackRecommendation = RollbackRecommendation.HOLD_FOR_REVIEW
    approval_actor: str | None = None
    rollback_receipt_id: str | None = None
    verification_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
