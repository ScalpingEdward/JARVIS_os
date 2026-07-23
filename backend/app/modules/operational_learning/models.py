from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class LearningState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ANALYZED = "analyzed"
    RECOMMENDATIONS_PROPOSED = "recommendations-proposed"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    APPLIED = "applied"
    VALIDATING = "validating"
    VERIFIED = "verified"
    REJECTED = "rejected"
    FAILED = "failed"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class OutcomeStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


class RecommendationType(str, Enum):
    THRESHOLD = "threshold"
    RETRY_POLICY = "retry-policy"
    RECOVERY_SELECTION = "recovery-selection"
    STABILIZATION = "stabilization"
    OBSERVABILITY = "observability"
    MANUAL_REVIEW = "manual-review"


class RecoveryOutcome(BaseModel):
    outcome_id: str = Field(min_length=1, max_length=160)
    supervisor_id: str = Field(min_length=1, max_length=180)
    orchestration_id: str | None = Field(default=None, max_length=180)
    status: OutcomeStatus
    recovery_attempts: int = Field(ge=0, le=100)
    time_to_recovery_seconds: int | None = Field(default=None, ge=0, le=604800)
    healthy_cycles: int = Field(default=0, ge=0, le=10000)
    trigger_fingerprint: str = Field(min_length=1, max_length=240)
    evidence_refs: list[str] = Field(min_length=1)
    metrics: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearningRecommendation(BaseModel):
    recommendation_id: str = Field(min_length=1, max_length=160)
    recommendation_type: RecommendationType
    target: str = Field(min_length=1, max_length=240)
    rationale: str = Field(min_length=1, max_length=1000)
    proposed_value: float | int | str | bool
    baseline_value: float | int | str | bool | None = None
    confidence: float = Field(ge=0, le=1)
    expected_impact: str = Field(min_length=1, max_length=500)
    rollback_condition: str = Field(min_length=1, max_length=500)
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearningCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    target_system: str = Field(min_length=1, max_length=240)
    outcomes: list[RecoveryOutcome] = Field(min_length=1)
    recommendations: list[LearningRecommendation] = Field(default_factory=list)
    minimum_sample_size: int = Field(default=3, ge=1, le=10000)
    minimum_confidence: float = Field(default=0.75, ge=0, le=1)
    validation_cycles_required: int = Field(default=3, ge=1, le=100)
    learning_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_learning(self) -> "LearningCreate":
        outcome_ids = [item.outcome_id for item in self.outcomes]
        if len(outcome_ids) != len(set(outcome_ids)):
            raise ValueError("outcome_id values must be unique")
        recommendation_ids = [item.recommendation_id for item in self.recommendations]
        if len(recommendation_ids) != len(set(recommendation_ids)):
            raise ValueError("recommendation_id values must be unique")
        return self


class LearningActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|analyze|propose|request-review|approve|apply|record-validation|verify|reject|fail|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    recommendation_ids: list[str] = Field(default_factory=list)
    validation_healthy: bool | None = None
    validation_evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: LearningState | None = None
    to_state: LearningState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class OperationalLearningRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    target_system: str
    outcomes: list[RecoveryOutcome]
    recommendations: list[LearningRecommendation]
    minimum_sample_size: int
    minimum_confidence: float
    validation_cycles_required: int
    learning_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: LearningState = LearningState.DRAFT
    selected_recommendation_ids: list[str] = Field(default_factory=list)
    approval_actor: str | None = None
    validation_cycles: int = 0
    consecutive_healthy_cycles: int = 0
    validation_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
