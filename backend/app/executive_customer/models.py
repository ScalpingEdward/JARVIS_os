from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class CustomerRisk(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class CustomerSegment(BaseModel):
    segment_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    customers: int = Field(ge=0)
    annual_revenue: float = Field(ge=0)
    gross_margin: float = Field(ge=0, le=100)
    retention_rate: float = Field(ge=0, le=100)
    expansion_rate: float = Field(ge=-100, le=1000)
    acquisition_cost: float = Field(ge=0)
    lifetime_value: float = Field(ge=0)
    strategic_importance: float = Field(ge=0, le=100)


class CustomerSignal(BaseModel):
    signal_id: str = Field(min_length=1, max_length=100)
    segment_id: str = Field(min_length=1, max_length=100)
    churn_probability: float = Field(ge=0, le=100)
    revenue_at_risk: float = Field(ge=0)
    satisfaction_score: float = Field(ge=0, le=100)
    description: str = Field(min_length=1, max_length=500)


class CustomerPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=100)
    strategy_plan_id: UUID | None = None
    market_portfolio_id: UUID | None = None
    capital_portfolio_id: UUID | None = None
    segments: list[CustomerSegment] = Field(min_length=1)
    signals: list[CustomerSignal] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self):
        segment_ids = [segment.segment_id for segment in self.segments]
        if len(segment_ids) != len(set(segment_ids)):
            raise ValueError("Duplicate customer segment id")
        signal_ids = [signal.signal_id for signal in self.signals]
        if len(signal_ids) != len(set(signal_ids)):
            raise ValueError("Duplicate customer signal id")
        unknown = {signal.segment_id for signal in self.signals} - set(segment_ids)
        if unknown:
            raise ValueError("Customer signal references unknown segment")
        return self


class CustomerSignalUpdate(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    signal_id: str = Field(min_length=1, max_length=100)
    churn_probability: float | None = Field(default=None, ge=0, le=100)
    revenue_at_risk: float | None = Field(default=None, ge=0)
    satisfaction_score: float | None = Field(default=None, ge=0, le=100)


class ExecutiveCustomerPortfolio(CustomerPortfolioCreate):
    portfolio_id: UUID = Field(default_factory=uuid4)
    total_revenue: float = 0
    weighted_retention: float = 0
    weighted_expansion: float = 0
    revenue_at_risk: float = 0
    customer_value_score: float = 0
    growth_score: float = 0
    vulnerable_segments: list[str] = Field(default_factory=list)
    expansion_segments: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    assessed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    autonomous_actions_enabled: bool = False


class CustomerListResponse(BaseModel):
    items: list[ExecutiveCustomerPortfolio]
    count: int


class CustomerStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    assessed_portfolios: int
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    actor_id: str
    action: str
    portfolio_id: UUID
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
