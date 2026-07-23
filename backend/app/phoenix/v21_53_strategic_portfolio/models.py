from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class PortfolioState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ANALYZED = "analyzed"
    ALLOCATION_READY = "allocation-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ORCHESTRATING = "orchestrating"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class AllocationStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


class PortfolioSleeve(BaseModel):
    sleeve_id: str = Field(min_length=1, max_length=180)
    strategy_id: str = Field(min_length=1, max_length=180)
    name: str = Field(min_length=1, max_length=240)
    target_weight: float = Field(ge=0, le=1)
    minimum_weight: float = Field(default=0, ge=0, le=1)
    maximum_weight: float = Field(default=1, ge=0, le=1)
    expected_return: float = Field(ge=-1, le=10)
    expected_volatility: float = Field(ge=0, le=10)
    liquidity_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    status: AllocationStatus = AllocationStatus.PROPOSED
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExposureConstraint(BaseModel):
    constraint_id: str = Field(min_length=1, max_length=180)
    dimension: str = Field(min_length=1, max_length=180)
    current_exposure: float = Field(ge=-10, le=10)
    maximum_absolute_exposure: float = Field(gt=0, le=10)
    evidence_refs: list[str] = Field(min_length=1)


class CorrelationPair(BaseModel):
    left_sleeve_id: str = Field(min_length=1, max_length=180)
    right_sleeve_id: str = Field(min_length=1, max_length=180)
    correlation: float = Field(ge=-1, le=1)


class StrategicPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    executive_record_id: str = Field(min_length=1, max_length=180)
    portfolio_name: str = Field(min_length=1, max_length=240)
    total_capital: float = Field(gt=0)
    sleeves: list[PortfolioSleeve] = Field(min_length=1)
    exposure_constraints: list[ExposureConstraint] = Field(default_factory=list)
    correlations: list[CorrelationPair] = Field(default_factory=list)
    minimum_sleeve_confidence: float = Field(default=0.8, ge=0, le=1)
    maximum_single_sleeve_weight: float = Field(default=0.4, gt=0, le=1)
    maximum_pair_correlation: float = Field(default=0.85, ge=0, le=1)
    minimum_liquidity_score: float = Field(default=0.5, ge=0, le=1)
    maximum_constraint_breaches: int = Field(default=0, ge=0)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    portfolio_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_portfolio(self) -> "StrategicPortfolioCreate":
        sleeve_ids = [item.sleeve_id for item in self.sleeves]
        if len(sleeve_ids) != len(set(sleeve_ids)):
            raise ValueError("sleeve_id values must be unique")
        if abs(sum(item.target_weight for item in self.sleeves) - 1.0) > 0.0001:
            raise ValueError("target weights must sum to 1")
        known = set(sleeve_ids)
        for item in self.sleeves:
            if not item.minimum_weight <= item.target_weight <= item.maximum_weight:
                raise ValueError("target weight must be within sleeve bounds")
        for pair in self.correlations:
            if pair.left_sleeve_id == pair.right_sleeve_id:
                raise ValueError("correlation pair must reference different sleeves")
            if pair.left_sleeve_id not in known or pair.right_sleeve_id not in known:
                raise ValueError("correlation pair must reference known sleeves")
        return self


class PortfolioActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|analyze|prepare-allocation|request-review|approve|orchestrate|record-cycle|verify|escalate|suspend|resume|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    cycle_healthy: bool | None = None
    observed_turnover: float | None = Field(default=None, ge=0, le=10)
    observed_constraint_breaches: int | None = Field(default=None, ge=0)
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: PortfolioState | None = None
    to_state: PortfolioState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class StrategicPortfolioRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    executive_record_id: str
    portfolio_name: str
    total_capital: float
    sleeves: list[PortfolioSleeve]
    exposure_constraints: list[ExposureConstraint]
    correlations: list[CorrelationPair]
    minimum_sleeve_confidence: float
    maximum_single_sleeve_weight: float
    maximum_pair_correlation: float
    minimum_liquidity_score: float
    maximum_constraint_breaches: int
    required_healthy_cycles: int
    portfolio_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: PortfolioState = PortfolioState.DRAFT
    concentration_breaches: int = 0
    correlation_breaches: int = 0
    liquidity_breaches: int = 0
    constraint_breaches: int = 0
    consecutive_healthy_cycles: int = 0
    approval_actor: str | None = None
    orchestration_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
