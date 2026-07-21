from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PortfolioExposureState(str, Enum):
    BLOCKED = "blocked"
    TRADING_WINDOW_REQUIRED = "trading-window-required"
    SNAPSHOT_STALE = "snapshot-stale"
    POSITION_DATA_INVALID = "position-data-invalid"
    CORRELATION_DATA_STALE = "correlation-data-stale"
    CORRELATION_LIMIT_EXCEEDED = "correlation-limit-exceeded"
    SYMBOL_EXPOSURE_EXCEEDED = "symbol-exposure-exceeded"
    CURRENCY_EXPOSURE_EXCEEDED = "currency-exposure-exceeded"
    DIRECTIONAL_EXPOSURE_EXCEEDED = "directional-exposure-exceeded"
    PORTFOLIO_RISK_EXCEEDED = "portfolio-risk-exceeded"
    MARGIN_REJECTED = "margin-rejected"
    RISK_REJECTED = "risk-rejected"
    APPROVAL_REQUIRED = "approval-required"
    REBALANCE_REQUIRED = "rebalance-required"
    PORTFOLIO_READY = "portfolio-ready"
    FAILED = "failed"


class PositionExposure(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    side: str = Field(pattern="^(buy|sell)$")
    volume: float = Field(gt=0)
    notional: float = Field(gt=0)
    risk_amount: float = Field(ge=0)
    base_currency: str = Field(min_length=3, max_length=8)
    quote_currency: str = Field(min_length=3, max_length=8)


class CorrelationPair(BaseModel):
    symbol_a: str = Field(min_length=1, max_length=32)
    symbol_b: str = Field(min_length=1, max_length=32)
    coefficient: float = Field(ge=-1, le=1)


class PortfolioExposureAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    trading_window_ready: bool
    snapshot_age_seconds: int = Field(ge=0)
    max_snapshot_age_seconds: int = Field(default=15, ge=1)
    correlation_age_seconds: int = Field(ge=0)
    max_correlation_age_seconds: int = Field(default=300, ge=1)
    positions: list[PositionExposure] = Field(default_factory=list)
    correlations: list[CorrelationPair] = Field(default_factory=list)
    proposed_symbol: str = Field(min_length=1, max_length=32)
    proposed_side: str = Field(pattern="^(buy|sell)$")
    proposed_notional: float = Field(gt=0)
    proposed_risk_amount: float = Field(ge=0)
    proposed_base_currency: str = Field(min_length=3, max_length=8)
    proposed_quote_currency: str = Field(min_length=3, max_length=8)
    max_pair_correlation: float = Field(default=0.80, ge=0, le=1)
    max_symbol_notional: float = Field(gt=0)
    max_currency_notional: float = Field(gt=0)
    max_directional_notional: float = Field(gt=0)
    max_portfolio_risk_amount: float = Field(gt=0)
    current_margin_level_percent: float = Field(gt=0)
    projected_margin_level_percent: float = Field(gt=0)
    minimum_margin_level_percent: float = Field(default=150, gt=0)
    rebalance_plan_defined: bool = False
    account_risk_approved: bool
    prop_rules_approved: bool
    risk_brain_blocked: bool = False
    human_approved: bool = False
    terminal_error: str | None = None


class PortfolioExposureExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    human_approved: bool | None = None
    rebalance_plan_defined: bool | None = None
    account_risk_approved: bool | None = None
    prop_rules_approved: bool | None = None
    projected_margin_level_percent: float | None = Field(default=None, gt=0)
    terminal_error: str | None = None


class PortfolioExposureAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    state: PortfolioExposureState
    reasons: list[str] = Field(default_factory=list)
    payload: PortfolioExposureAssessmentCreate
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PortfolioExposureStatus(BaseModel):
    workspace_id: str
    latest_state: PortfolioExposureState | None
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    record_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
