from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class PositionState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    PLANNED = "planned"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    OPEN = "open"
    PROTECTED = "protected"
    SCALING_OUT = "scaling-out"
    EXIT_RECOMMENDED = "exit-recommended"
    CLOSED = "closed"
    INVALIDATED = "invalidated"
    ARCHIVED = "archived"


class ExitRule(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    kind: Literal["take-profit", "break-even", "atr-trail", "swing-trail", "time-exit", "news-exit", "structure-exit"]
    trigger_price: float | None = None
    close_percent: float = Field(default=0, ge=0, le=100)
    stop_price: float | None = None
    max_hold_minutes: int | None = Field(default=None, ge=1)
    evidence_ref: str = Field(min_length=1, max_length=500)


class PositionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    trade_setup_record_id: str = Field(min_length=1, max_length=180)
    v21_15_approved: bool
    v21_15_evidence: dict[str, Any] = Field(default_factory=dict)
    symbol: str = Field(min_length=1, max_length=40)
    direction: Literal["long", "short"]
    entry_price: float
    initial_stop_price: float
    position_size: float = Field(gt=0)
    risk_amount: float = Field(gt=0)
    exit_rules: list[ExitRule] = Field(min_length=1)
    active_news_risk: bool = False
    risk_brain_hard_block: bool = False

    @model_validator(mode="after")
    def validate_geometry(self) -> "PositionCreate":
        if self.direction == "long" and self.initial_stop_price >= self.entry_price:
            raise ValueError("long stop must be below entry")
        if self.direction == "short" and self.initial_stop_price <= self.entry_price:
            raise ValueError("short stop must be above entry")
        if sum(rule.close_percent for rule in self.exit_rules) > 100:
            raise ValueError("exit close percentages cannot exceed 100")
        return self


class PositionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    trade_setup_record_id: str
    symbol: str
    direction: Literal["long", "short"]
    state: PositionState
    entry_price: float
    current_stop_price: float
    position_size: float
    remaining_percent: float = 100
    risk_amount: float
    realized_r_multiple: float = 0
    active_rule_keys: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    approval_token: str | None = None
    downstream_receipt: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PositionCommand(str, Enum):
    APPROVE = "approve"
    MARK_OPEN = "mark-open"
    APPLY_RULE = "apply-rule"
    RECOMMEND_EXIT = "recommend-exit"
    CLOSE = "close"
    INVALIDATE = "invalidate"
    ARCHIVE = "archive"


class PositionAction(BaseModel):
    command: PositionCommand
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = None
    downstream_receipt: str | None = None
    rule_key: str | None = None
    observed_price: float | None = None
    realized_r_multiple: float | None = None
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
