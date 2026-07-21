from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class RiskState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    ANALYSIS_PENDING = "analysis-pending"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    RISK_REGISTER_READY = "risk-register-ready"
    APPROVED = "approved"
    ISSUED_TO_INVESTMENT_DECISION = "issued-to-investment-decision"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    FAILED = "failed"


class RiskSignal(BaseModel):
    signal_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(min_length=3, max_length=160)
    category: Literal[
        "strategic", "financial", "delivery", "technical", "security",
        "compliance", "operational", "reputational", "dependency"
    ]
    probability: float = Field(ge=0, le=1)
    impact: float = Field(ge=0, le=100)
    velocity: float = Field(default=50, ge=0, le=100)
    detectability: float = Field(default=50, ge=0, le=100)
    owner: str = Field(min_length=2, max_length=120)
    mitigation: str = Field(min_length=3, max_length=1000)
    contingency: str = Field(min_length=3, max_length=1000)
    dependency_blocked: bool = False


class StrategicRiskCreate(BaseModel):
    workspace_id: str = Field(min_length=2, max_length=120)
    source_key: str = Field(min_length=3, max_length=180)
    executive_kpi_record_id: str = Field(min_length=3, max_length=180)
    executive_kpi_approved: bool
    executive_kpi_evidence: list[str] = Field(default_factory=list)
    risk_brain_status: Literal["clear", "review", "blocked"] = "clear"
    portfolio_confidence: float = Field(ge=0, le=100)
    risk_appetite: float = Field(default=50, ge=0, le=100)
    max_residual_exposure: float = Field(default=35, ge=0, le=100)
    signals: list[RiskSignal] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_upstream(self) -> "StrategicRiskCreate":
        if self.executive_kpi_approved and not self.executive_kpi_evidence:
            raise ValueError("approved v21.06 KPI input requires evidence")
        return self


class RiskAssessment(BaseModel):
    signal_id: str
    inherent_score: float
    mitigation_strength: float
    residual_score: float
    severity: Literal["low", "moderate", "high", "critical"]
    treatment: Literal["accept", "mitigate", "transfer", "avoid", "escalate"]
    rationale: str


class StrategicRiskRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    executive_kpi_record_id: str
    state: RiskState
    portfolio_confidence: float
    risk_appetite: float
    max_residual_exposure: float
    assessments: list[RiskAssessment] = Field(default_factory=list)
    aggregate_inherent_risk: float = 0
    aggregate_residual_risk: float = 0
    concentration_score: float = 0
    critical_risk_count: int = 0
    approval_token: str | None = None
    downstream_receipt: str | None = None
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StrategicRiskExecute(BaseModel):
    action: Literal["analyze", "approve", "reject", "issue", "archive"]
    actor: str = Field(min_length=2, max_length=120)
    approval_token: str | None = None
    receipt: str | None = None
    reason: str | None = Field(default=None, max_length=1000)


class AuditEntry(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    record_id: str
    action: str
    actor: str
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
