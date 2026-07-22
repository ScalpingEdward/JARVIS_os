from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class SetupState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    QUALIFICATION_PENDING = "qualification-pending"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    QUALIFIED = "qualified"
    APPROVED = "approved"
    ISSUED_TO_VISUALIZER = "issued-to-visualizer"
    REJECTED = "rejected"
    INVALIDATED = "invalidated"
    ARCHIVED = "archived"


class ConfirmationSignal(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    category: Literal[
        "structure", "liquidity", "imbalance", "order-flow", "session",
        "momentum", "volume", "risk", "news", "execution"
    ]
    present: bool
    weight: float = Field(default=1.0, gt=0, le=20)
    evidence_ref: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=1000)


class TradeSetupCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    market_structure_record_id: str = Field(min_length=1, max_length=180)
    v21_14_approved: bool
    v21_14_evidence: dict[str, Any] = Field(default_factory=dict)
    symbol: str = Field(min_length=1, max_length=40)
    timeframe: str = Field(min_length=1, max_length=20)
    direction: Literal["long", "short", "neutral"]
    entry_price: float
    stop_price: float
    target_prices: list[float] = Field(min_length=1, max_length=10)
    confidence_score: float = Field(ge=0, le=100)
    minimum_rr: float = Field(default=1.5, gt=0, le=100)
    minimum_confirmation_score: float = Field(default=70, ge=0, le=100)
    spread_points: float = Field(default=0, ge=0)
    maximum_spread_points: float = Field(default=100, ge=0)
    active_news_risk: bool = False
    session_allowed: bool = True
    risk_brain_hard_block: bool = False
    confirmations: list[ConfirmationSignal] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_geometry_and_keys(self) -> "TradeSetupCreate":
        keys = [item.key for item in self.confirmations]
        if len(keys) != len(set(keys)):
            raise ValueError("confirmation keys must be unique")
        if self.direction == "long":
            if self.stop_price >= self.entry_price:
                raise ValueError("long stop must be below entry")
            if any(target <= self.entry_price for target in self.target_prices):
                raise ValueError("long targets must be above entry")
        elif self.direction == "short":
            if self.stop_price <= self.entry_price:
                raise ValueError("short stop must be above entry")
            if any(target >= self.entry_price for target in self.target_prices):
                raise ValueError("short targets must be below entry")
        return self


class QualificationResult(BaseModel):
    confirmation_score: float
    risk_reward_ratios: list[float]
    passed_confirmations: list[str] = Field(default_factory=list)
    failed_confirmations: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    setup_grade: Literal["A+", "A", "B", "C", "rejected"]


class TradeSetupRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    market_structure_record_id: str
    symbol: str
    timeframe: str
    direction: str
    state: SetupState
    entry_price: float
    stop_price: float
    target_prices: list[float]
    confidence_score: float
    qualification: QualificationResult
    approval_token: str | None = None
    downstream_receipt: str | None = None
    notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SetupCommand(str, Enum):
    APPROVE = "approve"
    ISSUE = "issue"
    REJECT = "reject"
    INVALIDATE = "invalidate"
    ARCHIVE = "archive"


class SetupAction(BaseModel):
    command: SetupCommand
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = None
    downstream_receipt: str | None = None
    reason: str | None = Field(default=None, max_length=4000)


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    record_id: str
    action: str
    actor: str
    from_state: str | None = None
    to_state: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
