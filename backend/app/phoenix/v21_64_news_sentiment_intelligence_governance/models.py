from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NewsSentimentState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    SCORED = "scored"
    POLICY_READY = "policy-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    STABLE = "stable"
    NARRATIVE_SHIFT = "narrative-shift"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class NewsSignal(BaseModel):
    signal_id: str = Field(min_length=1)
    source_type: Literal[
        "wire", "publisher", "central-bank", "regulator", "company-filing",
        "earnings-call", "research", "social", "forum", "blog", "broadcast"
    ]
    entity: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    sentiment: float = Field(ge=-100, le=100)
    relevance: float = Field(ge=0, le=100)
    credibility: float = Field(ge=0, le=100)
    freshness: float = Field(ge=0, le=100)
    novelty: float = Field(ge=0, le=100)
    market_impact: float = Field(ge=0, le=100)
    manipulation_risk: float = Field(default=0, ge=0, le=100)


class NewsSentimentPolicy(BaseModel):
    minimum_quality_score: float = Field(default=60, ge=0, le=100)
    minimum_confidence_score: float = Field(default=55, ge=0, le=100)
    narrative_shift_threshold: float = Field(default=30, ge=0, le=100)
    escalation_impact_threshold: float = Field(default=85, ge=0, le=100)
    maximum_manipulation_risk: float = Field(default=65, ge=0, le=100)
    stable_cycles_required: int = Field(default=3, ge=1, le=20)


class NewsSentimentCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    signals: list[NewsSignal] = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    policy: NewsSentimentPolicy = Field(default_factory=NewsSentimentPolicy)
    risk_brain_blocked: bool = False

    @model_validator(mode="after")
    def validate_signals(self) -> "NewsSentimentCreate":
        ids = {item.signal_id for item in self.signals}
        if len(ids) != len(self.signals):
            raise ValueError("signal_id values must be unique")
        return self


class NewsSentimentAction(BaseModel):
    action: Literal[
        "prepare-evidence", "score", "prepare-policy", "request-review", "approve",
        "activate", "observe", "confirm-stable", "escalate", "suspend", "resume",
        "revoke", "archive"
    ]
    actor: str = Field(min_length=1)
    approval_token: str | None = None
    operation_receipt: str | None = None
    signals: list[NewsSignal] | None = None
    note: str | None = None


class NewsSentimentRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    subject: str
    signals: list[NewsSignal]
    evidence_refs: list[str]
    policy: NewsSentimentPolicy
    risk_brain_blocked: bool
    state: NewsSentimentState = NewsSentimentState.DRAFT
    sentiment_score: float = 0
    impact_score: float = 0
    quality_score: float = 0
    confidence_score: float = 0
    narrative_dispersion: float = 0
    manipulation_risk: float = 0
    violations: list[str] = Field(default_factory=list)
    stable_cycles: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: NewsSentimentState
    to_state: NewsSentimentState
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
