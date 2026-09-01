from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JournalState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    ANALYSIS_PENDING = "analysis-pending"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    ANALYZED = "analyzed"
    APPROVED = "approved"
    ISSUED = "issued-to-performance-intelligence"
    REJECTED = "rejected"
    INVALIDATED = "invalidated"
    ARCHIVED = "archived"


class TradeOutcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


class JournalCommand(str, Enum):
    APPROVE = "approve"
    ISSUE = "issue"
    REJECT = "reject"
    INVALIDATE = "invalidate"
    ARCHIVE = "archive"


class TradeJournalCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=120)
    source_key: str = Field(..., min_length=1, max_length=240)
    exposure_record_id: str = Field(..., min_length=1, max_length=120)
    position_record_id: str = Field(..., min_length=1, max_length=120)
    symbol: str = Field(..., min_length=2, max_length=32)
    direction: str = Field(..., pattern="^(long|short)$")
    setup_grade: str = Field(..., pattern="^(A\\+|A|B|C)$")
    confidence_score: float = Field(..., ge=0, le=100)
    planned_risk_percent: float = Field(..., gt=0, le=10)
    realized_r_multiple: float = Field(..., ge=-20, le=100)
    holding_minutes: int = Field(..., ge=0, le=100000)
    session: str = Field(..., min_length=1, max_length=60)
    strategy_tags: List[str] = Field(default_factory=list, max_items=30)
    followed_plan: bool
    stop_respected: bool
    target_plan_respected: bool
    news_risk_present: bool = False
    notes: Optional[str] = Field(default=None, max_length=4000)
    upstream_evidence_verified: bool = False
    risk_brain_blocked: bool = False
    approval_token: Optional[str] = Field(default=None, max_length=240)

    @validator("symbol")
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @validator("strategy_tags", each_item=True)
    def normalize_tag(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError("strategy tags cannot be empty")
        return value


class JournalAction(BaseModel):
    command: JournalCommand
    actor: str = Field(..., min_length=1, max_length=120)
    approval_token: Optional[str] = Field(default=None, max_length=240)
    downstream_receipt: Optional[str] = Field(default=None, max_length=240)
    reason: Optional[str] = Field(default=None, max_length=1000)


class JournalAnalytics(BaseModel):
    outcome: TradeOutcome
    execution_quality_score: float = Field(..., ge=0, le=100)
    discipline_score: float = Field(..., ge=0, le=100)
    risk_efficiency_score: float = Field(..., ge=0, le=100)
    expectancy_contribution: float
    process_flags: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    improvement_actions: List[str] = Field(default_factory=list)


class TradeJournalRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    exposure_record_id: str
    position_record_id: str
    symbol: str
    direction: str
    setup_grade: str
    confidence_score: float
    planned_risk_percent: float
    realized_r_multiple: float
    holding_minutes: int
    session: str
    strategy_tags: List[str]
    followed_plan: bool
    stop_respected: bool
    target_plan_respected: bool
    news_risk_present: bool
    notes: Optional[str]
    state: JournalState
    analytics: Optional[JournalAnalytics] = None
    approval_token: Optional[str] = None
    downstream_receipt: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    record_id: str
    action: str
    actor: str
    from_state: Optional[JournalState] = None
    to_state: JournalState
    details: Dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
