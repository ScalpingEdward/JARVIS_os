from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OptimizerState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    ANALYSIS_PENDING = "analysis-pending"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    RECOMMENDATION_READY = "recommendation-ready"
    APPROVED = "approved"
    ISSUED = "issued-to-strategy-governance"
    REJECTED = "rejected"
    INVALIDATED = "invalidated"
    ARCHIVED = "archived"


class OptimizerCommand(str, Enum):
    APPROVE = "approve"
    ISSUE = "issue"
    REJECT = "reject"
    INVALIDATE = "invalidate"
    ARCHIVE = "archive"


class PerformanceSample(BaseModel):
    symbol: str = Field(..., min_length=2, max_length=32)
    session: str = Field(..., min_length=1, max_length=60)
    strategy_tag: str = Field(..., min_length=1, max_length=120)
    setup_grade: str = Field(..., pattern="^(A\\+|A|B|C)$")
    realized_r_multiple: float = Field(..., ge=-20, le=100)
    execution_quality_score: float = Field(..., ge=0, le=100)
    discipline_score: float = Field(..., ge=0, le=100)
    risk_efficiency_score: float = Field(..., ge=0, le=100)

    @validator("symbol")
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @validator("strategy_tag")
    def normalize_tag(cls, value: str) -> str:
        return value.strip().lower()


class OptimizerCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=120)
    source_key: str = Field(..., min_length=1, max_length=240)
    journal_record_ids: List[str] = Field(..., min_items=3, max_items=1000)
    samples: List[PerformanceSample] = Field(..., min_items=3, max_items=1000)
    minimum_sample_size: int = Field(default=10, ge=3, le=500)
    max_risk_change_percent: float = Field(default=20, gt=0, le=50)
    upstream_evidence_verified: bool = False
    risk_brain_blocked: bool = False


class OptimizerAction(BaseModel):
    command: OptimizerCommand
    actor: str = Field(..., min_length=1, max_length=120)
    approval_token: Optional[str] = Field(default=None, max_length=240)
    downstream_receipt: Optional[str] = Field(default=None, max_length=240)
    reason: Optional[str] = Field(default=None, max_length=1000)


class SegmentMetric(BaseModel):
    segment: str
    trades: int
    win_rate: float
    average_r: float
    expectancy_r: float
    execution_quality: float
    discipline: float
    risk_efficiency: float


class OptimizationRecommendation(BaseModel):
    confidence_score: float = Field(..., ge=0, le=100)
    sample_size: int
    preferred_segments: List[str] = Field(default_factory=list)
    suppressed_segments: List[str] = Field(default_factory=list)
    risk_multiplier: float = Field(..., ge=0.5, le=1.5)
    recommendations: List[str] = Field(default_factory=list)
    safeguards: List[str] = Field(default_factory=list)
    metrics: List[SegmentMetric] = Field(default_factory=list)


class OptimizerRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    journal_record_ids: List[str]
    state: OptimizerState
    recommendation: Optional[OptimizationRecommendation] = None
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
    from_state: Optional[OptimizerState] = None
    to_state: OptimizerState
    details: Dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
