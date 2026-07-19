from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class DataQuality(str, Enum):
    simulated = "simulated"
    broker_tick = "broker_tick"
    consolidated = "consolidated"
    exchange = "exchange"


class MarketSide(str, Enum):
    buy = "buy"
    sell = "sell"
    neutral = "neutral"


class PriceLevel(BaseModel):
    price: float
    bid_volume: float = Field(ge=0)
    ask_volume: float = Field(ge=0)

    @property
    def delta(self) -> float:
        return self.ask_volume - self.bid_volume


class OrderFlowSnapshot(BaseModel):
    snapshot_id: UUID = Field(default_factory=uuid4)
    symbol: str = Field(min_length=1, max_length=30)
    venue: str = Field(min_length=1, max_length=80)
    data_quality: DataQuality
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    levels: list[PriceLevel] = Field(min_length=1)
    open_interest: float | None = Field(default=None, ge=0)
    best_bid: float | None = None
    best_ask: float | None = None

    @model_validator(mode="after")
    def validate_book(self) -> "OrderFlowSnapshot":
        if self.best_bid is not None and self.best_ask is not None and self.best_ask < self.best_bid:
            raise ValueError("best_ask must be greater than or equal to best_bid")
        return self


class MicrostructureRisk(BaseModel):
    risk_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=120)
    severity: float = Field(ge=0, le=100)
    probability: float = Field(ge=0, le=100)
    evidence: list[str] = Field(default_factory=list)
    remediation: str | None = Field(default=None, max_length=500)


class OrderFlowPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=120)
    snapshots: list[OrderFlowSnapshot] = Field(min_length=1)
    risks: list[MicrostructureRisk] = Field(default_factory=list)
    trading_portfolio_ref: UUID | None = None
    strategy_portfolio_ref: UUID | None = None


class OrderFlowRiskUpdate(BaseModel):
    risk_id: UUID
    severity: float | None = Field(default=None, ge=0, le=100)
    probability: float | None = Field(default=None, ge=0, le=100)
    remediation: str | None = Field(default=None, max_length=500)
    actor_id: str = Field(min_length=1, max_length=100)


class OrderFlowAssessment(BaseModel):
    cumulative_delta: float
    delta_ratio: float = Field(ge=-1, le=1)
    imbalance_score: float = Field(ge=0, le=100)
    absorption_score: float = Field(ge=0, le=100)
    liquidity_quality_score: float = Field(ge=0, le=100)
    data_reliability_score: float = Field(ge=0, le=100)
    risk_exposure_score: float = Field(ge=0, le=100)
    directional_bias: MarketSide
    no_trade: bool
    reasons: list[str]
    recommendations: list[str]


class ExecutiveOrderFlowPortfolio(BaseModel):
    portfolio_id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    name: str
    snapshots: list[OrderFlowSnapshot]
    risks: list[MicrostructureRisk]
    trading_portfolio_ref: UUID | None = None
    strategy_portfolio_ref: UUID | None = None
    assessment: OrderFlowAssessment | None = None
    autonomous_execution_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrderFlowListResponse(BaseModel):
    items: list[ExecutiveOrderFlowPortfolio]
    count: int


class OrderFlowStatusResponse(BaseModel):
    workspace_id: str
    portfolio_count: int
    snapshot_count: int
    exchange_quality_snapshot_count: int
    autonomous_execution_enabled: bool = False


class AuditRecord(BaseModel):
    audit_id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    portfolio_id: UUID
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
