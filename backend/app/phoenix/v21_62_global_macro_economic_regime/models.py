from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MacroState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    CLASSIFIED = "classified"
    POLICY_READY = "policy-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    STABLE = "stable"
    REGIME_SHIFT = "regime-shift"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class MacroIndicator(BaseModel):
    name: str = Field(min_length=1)
    category: Literal[
        "growth", "inflation", "employment", "rates", "yield-curve",
        "liquidity", "currency", "commodity", "credit", "sentiment"
    ]
    region: str = Field(min_length=1)
    value: float
    previous_value: float
    normalized_score: float = Field(ge=-100, le=100)
    surprise_score: float = Field(default=0, ge=-100, le=100)
    freshness_minutes: int = Field(default=0, ge=0)
    source_ref: str = Field(min_length=1)


class CentralBankSignal(BaseModel):
    bank: Literal["FED", "ECB", "BOJ", "BOE", "SNB", "RBA", "RBNZ", "PBOC", "BOC"]
    policy_rate: float
    expected_rate: float
    stance: Literal["very-dovish", "dovish", "neutral", "hawkish", "very-hawkish"]
    balance_sheet_impulse: float = Field(default=0, ge=-100, le=100)
    confidence: float = Field(default=50, ge=0, le=100)


class AssetMacroScore(BaseModel):
    asset: str = Field(min_length=1)
    growth_sensitivity: float = Field(default=0, ge=-100, le=100)
    inflation_sensitivity: float = Field(default=0, ge=-100, le=100)
    rate_sensitivity: float = Field(default=0, ge=-100, le=100)
    liquidity_sensitivity: float = Field(default=0, ge=-100, le=100)
    currency_sensitivity: float = Field(default=0, ge=-100, le=100)


class MacroPolicy(BaseModel):
    minimum_data_quality: float = Field(default=65, ge=0, le=100)
    maximum_indicator_age_minutes: int = Field(default=1440, ge=1)
    regime_shift_threshold: float = Field(default=25, ge=1, le=100)
    escalation_risk_threshold: float = Field(default=80, ge=0, le=100)
    stable_cycles_required: int = Field(default=3, ge=1, le=20)
    require_human_approval: bool = True


class MacroCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    indicators: list[MacroIndicator] = Field(min_length=1)
    central_banks: list[CentralBankSignal] = Field(default_factory=list)
    assets: list[AssetMacroScore] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    policy: MacroPolicy = Field(default_factory=MacroPolicy)
    risk_brain_blocked: bool = False

    @model_validator(mode="after")
    def validate_unique_inputs(self) -> "MacroCreate":
        indicator_keys = {(item.name, item.region) for item in self.indicators}
        if len(indicator_keys) != len(self.indicators):
            raise ValueError("indicator name and region combinations must be unique")
        banks = {item.bank for item in self.central_banks}
        if len(banks) != len(self.central_banks):
            raise ValueError("central bank values must be unique")
        return self


class MacroAction(BaseModel):
    action: Literal[
        "prepare-evidence", "classify", "prepare-policy", "request-review",
        "approve", "activate", "observe", "confirm-stable", "escalate",
        "suspend", "resume", "revoke", "archive"
    ]
    actor: str = Field(min_length=1)
    approval_token: str | None = None
    operation_receipt: str | None = None
    indicators: list[MacroIndicator] | None = None
    central_banks: list[CentralBankSignal] | None = None
    note: str | None = None


class MacroRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    indicators: list[MacroIndicator]
    central_banks: list[CentralBankSignal]
    assets: list[AssetMacroScore]
    evidence_refs: list[str]
    policy: MacroPolicy
    risk_brain_blocked: bool
    state: MacroState = MacroState.DRAFT
    regime: str = "unclassified"
    risk_environment: Literal["risk-on", "neutral", "risk-off"] = "neutral"
    growth_score: float = 0
    inflation_score: float = 0
    rates_score: float = 0
    liquidity_score: float = 0
    currency_score: float = 0
    macro_risk_score: float = 0
    data_quality_score: float = 0
    regime_confidence: float = 0
    violations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    stable_cycles: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: MacroState
    to_state: MacroState
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
