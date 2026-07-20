from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PortfolioState(str, Enum):
    blocked = "blocked"
    hold = "hold"
    balanced = "balanced"
    rebalance = "rebalance"
    fully_allocated = "fully-allocated"


class LiveExposurePosition(BaseModel):
    broker_id: str = Field(min_length=1, max_length=100)
    account_id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=30)
    strategy_id: str = Field(min_length=1, max_length=100)
    currency: str = Field(min_length=3, max_length=8)
    allocated_capital: float = Field(ge=0)
    risk_amount: float = Field(ge=0)
    correlation_group: str = Field(default="independent", min_length=1, max_length=100)


class PortfolioExposurePolicy(BaseModel):
    max_broker_share: float = Field(default=0.45, gt=0, le=1)
    max_symbol_share: float = Field(default=0.35, gt=0, le=1)
    max_strategy_share: float = Field(default=0.40, gt=0, le=1)
    max_currency_share: float = Field(default=0.60, gt=0, le=1)
    max_correlation_group_share: float = Field(default=0.50, gt=0, le=1)
    max_total_risk_share: float = Field(default=0.05, gt=0, le=1)
    max_portfolio_drawdown_share: float = Field(default=0.10, gt=0, le=1)


class LivePortfolioExposureCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    total_live_owned_capital: float = Field(gt=0)
    current_drawdown: float = Field(default=0, ge=0)
    human_approved: bool = False
    risk_brain_clear: bool = True
    positions: list[LiveExposurePosition] = Field(min_length=1)
    policy: PortfolioExposurePolicy

    @model_validator(mode="after")
    def validate_owned_capital(self):
        if sum(item.allocated_capital for item in self.positions) > self.total_live_owned_capital:
            raise ValueError("Allocated Live capital exceeds owned Live capital")
        return self


class ExposureLine(BaseModel):
    dimension: str
    key: str
    exposure_amount: float
    exposure_share: float
    limit_share: float
    breached: bool
    recommended_action: str


class PortfolioScores(BaseModel):
    portfolio_diversification: int = Field(ge=0, le=100)
    correlation_safety: int = Field(ge=0, le=100)
    symbol_concentration_safety: int = Field(ge=0, le=100)
    strategy_concentration_safety: int = Field(ge=0, le=100)
    portfolio_stability: int = Field(ge=0, le=100)
    capital_utilization: int = Field(ge=0, le=100)
    exposure_confidence: int = Field(ge=0, le=100)


class LivePortfolioExposureAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    state: PortfolioState
    total_live_owned_capital: float
    allocated_capital: float
    unallocated_capital: float
    total_risk_amount: float
    exposure_lines: list[ExposureLine]
    scores: PortfolioScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PortfolioStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: PortfolioState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
