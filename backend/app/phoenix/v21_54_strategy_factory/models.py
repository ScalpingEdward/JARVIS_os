from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class StrategyFactoryState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    RESEARCHED = "researched"
    VALIDATION_READY = "validation-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    INCUBATING = "incubating"
    MONITORING = "monitoring"
    PROMOTED = "promoted"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    RETIRED = "retired"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class CandidateStatus(str, Enum):
    PROPOSED = "proposed"
    RESEARCHED = "researched"
    VALIDATED = "validated"
    REJECTED = "rejected"
    INCUBATING = "incubating"
    PROMOTED = "promoted"
    RETIRED = "retired"


class StrategyCandidate(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=180)
    name: str = Field(min_length=1, max_length=240)
    owner: str = Field(min_length=1, max_length=180)
    market: str = Field(min_length=1, max_length=120)
    timeframe: str = Field(min_length=1, max_length=80)
    hypothesis: str = Field(min_length=1, max_length=1000)
    expected_alpha: float
    expected_sharpe: float = Field(ge=-10, le=20)
    maximum_drawdown: float = Field(ge=0, le=1)
    capacity_score: float = Field(ge=0, le=1)
    robustness_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    status: CandidateStatus = CandidateStatus.PROPOSED
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationGate(BaseModel):
    gate_id: str = Field(min_length=1, max_length=180)
    name: str = Field(min_length=1, max_length=240)
    passed: bool
    score: float = Field(ge=0, le=1)
    minimum_score: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(min_length=1)


class StrategyFactoryCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    portfolio_record_id: str = Field(min_length=1, max_length=180)
    program_name: str = Field(min_length=1, max_length=240)
    candidates: list[StrategyCandidate] = Field(min_length=1)
    validation_gates: list[ValidationGate] = Field(min_length=1)
    selected_candidate_id: str = Field(min_length=1, max_length=180)
    minimum_candidate_confidence: float = Field(default=0.85, ge=0, le=1)
    minimum_robustness_score: float = Field(default=0.8, ge=0, le=1)
    minimum_validation_pass_rate: float = Field(default=1, ge=0, le=1)
    maximum_allowed_drawdown: float = Field(default=0.15, ge=0, le=1)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    research_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_configuration(self) -> "StrategyFactoryCreate":
        candidate_ids = [item.candidate_id for item in self.candidates]
        gate_ids = [item.gate_id for item in self.validation_gates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate_id values must be unique")
        if len(gate_ids) != len(set(gate_ids)):
            raise ValueError("gate_id values must be unique")
        if self.selected_candidate_id not in set(candidate_ids):
            raise ValueError("selected_candidate_id must reference a known candidate")
        return self


class StrategyFactoryActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|research|prepare-validation|request-review|approve|incubate|record-cycle|promote|escalate|suspend|resume|retire|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    cycle_healthy: bool | None = None
    observed_alpha: float | None = None
    observed_sharpe: float | None = Field(default=None, ge=-10, le=20)
    observed_drawdown: float | None = Field(default=None, ge=0, le=1)
    observed_robustness: float | None = Field(default=None, ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: StrategyFactoryState | None = None
    to_state: StrategyFactoryState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class StrategyFactoryRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    portfolio_record_id: str
    program_name: str
    candidates: list[StrategyCandidate]
    validation_gates: list[ValidationGate]
    selected_candidate_id: str
    minimum_candidate_confidence: float
    minimum_robustness_score: float
    minimum_validation_pass_rate: float
    maximum_allowed_drawdown: float
    required_healthy_cycles: int
    research_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: StrategyFactoryState = StrategyFactoryState.DRAFT
    validation_pass_rate: float = 0
    selected_confidence: float = 0
    selected_robustness: float = 0
    selected_drawdown: float = 0
    approval_actor: str | None = None
    consecutive_healthy_cycles: int = 0
    incubation_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
