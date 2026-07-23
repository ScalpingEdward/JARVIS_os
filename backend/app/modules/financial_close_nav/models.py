from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class CloseState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    CALCULATED = "calculated"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    CLOSED = "closed"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    ESCALATED = "escalated"
    REOPENED = "reopened"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class ValuationStatus(str, Enum):
    PRICED = "priced"
    ESTIMATED = "estimated"
    STALE = "stale"
    MISSING = "missing"


class ValuationPosition(BaseModel):
    position_id: str = Field(min_length=1, max_length=180)
    account_id: str = Field(min_length=1, max_length=180)
    asset: str = Field(min_length=1, max_length=80)
    quantity: float
    unit_price: float = Field(ge=0)
    market_value: float = Field(ge=0)
    valuation_status: ValuationStatus = ValuationStatus.PRICED
    price_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PerformanceMetric(BaseModel):
    metric_id: str = Field(min_length=1, max_length=180)
    name: str = Field(min_length=1, max_length=180)
    value: float
    benchmark_value: float | None = None
    tolerance: float = Field(default=0, ge=0)
    evidence_refs: list[str] = Field(min_length=1)


class FinancialCloseCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    settlement_record_id: str = Field(min_length=1, max_length=180)
    close_name: str = Field(min_length=1, max_length=240)
    reporting_currency: str = Field(min_length=1, max_length=20)
    positions: list[ValuationPosition] = Field(min_length=1)
    metrics: list[PerformanceMetric] = Field(default_factory=list)
    cash_balance: float
    liabilities: float = Field(default=0, ge=0)
    accrued_fees: float = Field(default=0, ge=0)
    maximum_nav_variance: float = Field(default=0.01, ge=0, le=1)
    maximum_stale_price_ratio: float = Field(default=0.05, ge=0, le=1)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    close_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_records(self) -> "FinancialCloseCreate":
        position_ids = [item.position_id for item in self.positions]
        if len(position_ids) != len(set(position_ids)):
            raise ValueError("position_id values must be unique")
        metric_ids = [item.metric_id for item in self.metrics]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("metric_id values must be unique")
        return self


class CloseActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|calculate|request-review|approve|close|record-cycle|verify|escalate|reopen|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    calculated_nav: float | None = None
    external_nav: float | None = None
    cycle_healthy: bool | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: CloseState | None = None
    to_state: CloseState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class FinancialCloseRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    settlement_record_id: str
    close_name: str
    reporting_currency: str
    positions: list[ValuationPosition]
    metrics: list[PerformanceMetric]
    cash_balance: float
    liabilities: float
    accrued_fees: float
    maximum_nav_variance: float
    maximum_stale_price_ratio: float
    required_healthy_cycles: int
    close_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: CloseState = CloseState.DRAFT
    calculated_nav: float = 0
    external_nav: float | None = None
    nav_variance: float = 0
    approval_actor: str | None = None
    consecutive_healthy_cycles: int = 0
    verification_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
