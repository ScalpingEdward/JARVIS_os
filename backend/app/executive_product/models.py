from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ProductStage(str, Enum):
    discovery = "discovery"
    validation = "validation"
    development = "development"
    launch = "launch"
    scale = "scale"
    mature = "mature"
    sunset = "sunset"


class ProductLine(BaseModel):
    product_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    stage: ProductStage
    annual_revenue: float = Field(ge=0)
    gross_margin: float = Field(ge=-100, le=100)
    market_fit: float = Field(ge=0, le=100)
    strategic_alignment: float = Field(ge=0, le=100)
    growth_potential: float = Field(ge=0, le=100)
    technical_health: float = Field(ge=0, le=100)


class InnovationInitiative(BaseModel):
    initiative_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    owner_id: str = Field(min_length=1, max_length=100)
    investment_required: float = Field(ge=0)
    expected_annual_value: float = Field(ge=0)
    time_to_market_months: int = Field(ge=0, le=240)
    feasibility: float = Field(ge=0, le=100)
    customer_desirability: float = Field(ge=0, le=100)
    strategic_alignment: float = Field(ge=0, le=100)
    execution_risk: float = Field(ge=0, le=100)


class ProductPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    actor_id: str = Field(min_length=1, max_length=100)
    strategy_plan_id: UUID | None = None
    market_portfolio_id: UUID | None = None
    customer_portfolio_id: UUID | None = None
    capital_portfolio_id: UUID | None = None
    products: list[ProductLine] = Field(min_length=1)
    initiatives: list[InnovationInitiative] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_ids(self):
        product_ids = [item.product_id for item in self.products]
        initiative_ids = [item.initiative_id for item in self.initiatives]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Duplicate product id")
        if len(initiative_ids) != len(set(initiative_ids)):
            raise ValueError("Duplicate initiative id")
        return self


class InitiativeUpdate(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    initiative_id: str = Field(min_length=1, max_length=100)
    investment_required: float | None = Field(default=None, ge=0)
    expected_annual_value: float | None = Field(default=None, ge=0)
    feasibility: float | None = Field(default=None, ge=0, le=100)
    execution_risk: float | None = Field(default=None, ge=0, le=100)


class ExecutiveProductPortfolio(ProductPortfolioCreate):
    portfolio_id: UUID = Field(default_factory=uuid4)
    portfolio_health_score: float = 0
    innovation_readiness_score: float = 0
    growth_exposure_score: float = 0
    technical_debt_exposure: float = 0
    total_innovation_investment: float = 0
    expected_innovation_value: float = 0
    priority_initiatives: list[str] = Field(default_factory=list)
    review_products: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    assessed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    autonomous_actions_enabled: bool = False


class ProductListResponse(BaseModel):
    items: list[ExecutiveProductPortfolio]
    count: int


class ProductStatusResponse(BaseModel):
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
