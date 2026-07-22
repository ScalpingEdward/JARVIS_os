from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ReviewState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    DRAFT = "draft"
    ANALYZED = "analyzed"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    IMPROVEMENT_QUEUED = "improvement-queued"
    VERIFIED = "verified"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class FindingSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ResilienceFinding(BaseModel):
    finding_id: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=120)
    severity: FindingSeverity
    description: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[str] = Field(default_factory=list)
    recommended_action: str = Field(min_length=1, max_length=2000)


class ResilienceMetric(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    baseline_value: float
    observed_value: float
    target_value: float | None = None
    unit: str = Field(default="count", min_length=1, max_length=40)


class ResilienceReviewCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    incident_record_id: str = Field(min_length=1, max_length=120)
    reconciliation_record_id: str | None = Field(default=None, max_length=120)
    runtime_record_id: str | None = Field(default=None, max_length=120)
    upstream_evidence_verified: bool = False
    risk_brain_blocked: bool = False
    root_cause: str = Field(min_length=1, max_length=4000)
    impact_summary: str = Field(min_length=1, max_length=4000)
    findings: list[ResilienceFinding] = Field(default_factory=list)
    metrics: list[ResilienceMetric] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_duplicate_findings(self):
        ids = [item.finding_id for item in self.findings]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate resilience finding")
        return self


class ResilienceReviewAction(BaseModel):
    action: str = Field(pattern="^(analyze|approve|queue-improvement|verify|reject|archive)$")
    actor_id: str = Field(min_length=1, max_length=120)
    reason: str | None = Field(default=None, max_length=2000)
    approval_token: str | None = Field(default=None, max_length=500)
    receipt_id: str | None = Field(default=None, max_length=200)
    completed_finding_ids: list[str] = Field(default_factory=list)


class ResilienceReviewRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    incident_record_id: str
    reconciliation_record_id: str | None = None
    runtime_record_id: str | None = None
    root_cause: str
    impact_summary: str
    findings: list[ResilienceFinding]
    metrics: list[ResilienceMetric]
    state: ReviewState
    risk_brain_blocked: bool
    upstream_evidence_verified: bool
    resilience_score: float = 0.0
    critical_findings: int = 0
    completed_finding_ids: list[str] = Field(default_factory=list)
    approval_token_hash: str | None = None
    last_receipt_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditEvent(BaseModel):
    event_id: str
    record_id: str
    workspace_id: str
    action: str
    actor_id: str
    state: ReviewState
    reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
