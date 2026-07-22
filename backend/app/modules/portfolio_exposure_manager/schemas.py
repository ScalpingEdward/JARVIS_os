from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class ExposureState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    ASSESSMENT_PENDING = "assessment-pending"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    EXPOSURE_APPROVED = "exposure-approved"
    APPROVED = "approved"
    ISSUED_TO_EXECUTION_BOUNDARY = "issued-to-execution-boundary"
    REJECTED = "rejected"
    INVALIDATED = "invalidated"
    ARCHIVED = "archived"


class OpenPosition(BaseModel):
    position_id: str
    symbol: str
    side: Literal["long", "short"]
    risk_percent: float = Field(ge=0)
    notional_value: float = Field(ge=0)
    asset_class: str = "fx"
    base_currency: Optional[str] = None
    quote_currency: Optional[str] = None
    news_risk_active: bool = False


class PortfolioExposureRequest(BaseModel):
    workspace_id: str
    source_record_id: str
    source_key: str
    account_equity: float = Field(gt=0)
    proposed_symbol: str
    proposed_side: Literal["long", "short"]
    proposed_risk_percent: float = Field(gt=0)
    proposed_notional_value: float = Field(gt=0)
    proposed_asset_class: str = "fx"
    proposed_base_currency: Optional[str] = None
    proposed_quote_currency: Optional[str] = None
    proposed_news_risk_active: bool = False
    open_positions: List[OpenPosition] = Field(default_factory=list)
    correlation_matrix: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    max_total_risk_percent: float = Field(default=3.0, gt=0)
    max_correlated_risk_percent: float = Field(default=1.5, gt=0)
    max_asset_class_risk_percent: float = Field(default=2.0, gt=0)
    max_currency_risk_percent: float = Field(default=2.0, gt=0)
    max_same_direction_positions: int = Field(default=3, ge=1)
    correlation_threshold: float = Field(default=0.75, ge=0, le=1)
    max_news_exposed_positions: int = Field(default=1, ge=0)
    upstream_evidence_approved: bool = False
    risk_brain_hard_block: bool = False
    confidence_score: float = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_source(self) -> "PortfolioExposureRequest":
        if not self.source_record_id.strip() or not self.source_key.strip():
            raise ValueError("source evidence identifiers are required")
        return self


class ExposureDecision(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_record_id: str
    source_key: str
    state: ExposureState
    approved_risk_percent: float = 0
    portfolio_risk_percent: float = 0
    correlated_risk_percent: float = 0
    asset_class_risk_percent: float = 0
    currency_risk_percent: float = 0
    portfolio_heat_score: float = 0
    long_positions: int = 0
    short_positions: int = 0
    reasons: List[str] = Field(default_factory=list)
    requires_human_approval: bool = True
    approval_token: Optional[str] = None
    downstream_receipt: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExposureExecutionRequest(BaseModel):
    action: Literal["approve", "reject", "issue", "invalidate", "archive"]
    approval_token: Optional[str] = None
    downstream_receipt: Optional[str] = None
    actor: str = "human"
