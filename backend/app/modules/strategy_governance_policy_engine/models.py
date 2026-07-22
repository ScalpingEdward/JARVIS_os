from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GovernanceState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    POLICY_REVIEW_REQUIRED = "policy-review-required"
    POLICY_READY = "policy-ready"
    APPROVED = "approved"
    ACTIVATED = "activated"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled-back"
    INVALIDATED = "invalidated"
    ARCHIVED = "archived"


class GovernanceCommand(str, Enum):
    APPROVE = "approve"
    ACTIVATE = "activate"
    REJECT = "reject"
    ROLLBACK = "rollback"
    INVALIDATE = "invalidate"
    ARCHIVE = "archive"


class TradingWindow(BaseModel):
    weekday: int = Field(..., ge=0, le=6)
    start_minute_utc: int = Field(..., ge=0, le=1439)
    end_minute_utc: int = Field(..., ge=1, le=1440)


class StrategyPolicyCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=120)
    source_key: str = Field(..., min_length=1, max_length=240)
    optimizer_record_id: str = Field(..., min_length=1, max_length=120)
    strategy_id: str = Field(..., min_length=1, max_length=120)
    policy_version: int = Field(..., ge=1)
    symbols_allowed: List[str] = Field(..., min_length=1, max_length=200)
    symbols_blocked: List[str] = Field(default_factory=list, max_length=200)
    sessions_allowed: List[str] = Field(default_factory=list, max_length=50)
    setup_grades_allowed: List[str] = Field(default_factory=lambda: ["A+", "A"], max_length=4)
    minimum_confidence: float = Field(default=70, ge=0, le=100)
    max_risk_per_trade_percent: float = Field(default=1.0, gt=0, le=10)
    max_daily_risk_percent: float = Field(default=3.0, gt=0, le=20)
    max_open_positions: int = Field(default=3, ge=1, le=100)
    news_blackout_minutes_before: int = Field(default=15, ge=0, le=1440)
    news_blackout_minutes_after: int = Field(default=15, ge=0, le=1440)
    minimum_sample_size: int = Field(default=20, ge=3, le=10000)
    observed_sample_size: int = Field(..., ge=0, le=1000000)
    trading_windows: List[TradingWindow] = Field(default_factory=list, max_length=50)
    upstream_evidence_verified: bool = False
    risk_brain_blocked: bool = False

    @field_validator("symbols_allowed", "symbols_blocked")
    @classmethod
    def normalize_symbols(cls, values: List[str]) -> List[str]:
        normalized = [value.strip().upper() for value in values if value.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("duplicate symbols are not allowed")
        return normalized

    @field_validator("setup_grades_allowed")
    @classmethod
    def validate_grades(cls, values: List[str]) -> List[str]:
        allowed = {"A+", "A", "B", "C"}
        if not values or any(value not in allowed for value in values):
            raise ValueError("invalid setup grade")
        return values


class GovernanceAction(BaseModel):
    command: GovernanceCommand
    actor: str = Field(..., min_length=1, max_length=120)
    approval_token: Optional[str] = Field(default=None, max_length=240)
    activation_receipt: Optional[str] = Field(default=None, max_length=240)
    rollback_target_version: Optional[int] = Field(default=None, ge=1)
    reason: Optional[str] = Field(default=None, max_length=1000)


class PolicyAssessment(BaseModel):
    compliant: bool
    violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    effective_risk_cap_percent: float
    requires_human_review: bool = True


class StrategyPolicyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    optimizer_record_id: str
    strategy_id: str
    policy_version: int
    state: GovernanceState
    policy: StrategyPolicyCreate
    assessment: Optional[PolicyAssessment] = None
    approval_token: Optional[str] = None
    activation_receipt: Optional[str] = None
    previous_active_version: Optional[int] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    record_id: str
    action: str
    actor: str
    from_state: Optional[GovernanceState] = None
    to_state: GovernanceState
    details: Dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
