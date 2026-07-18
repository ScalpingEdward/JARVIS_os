from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


InvestmentStatus = Literal["proposed", "approved", "funded", "paused", "completed", "rejected"]
RiskLevel = Literal["low", "medium", "high", "critical"]


class BusinessCase(BaseModel):
    investment_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=160)
    owner_id: str = Field(min_length=1, max_length=100)
    requested_capital: float = Field(gt=0)
    expected_value: float = Field(ge=0)
    probability_of_success: float = Field(ge=0, le=1)
    strategic_alignment: float = Field(ge=0, le=100)
    time_to_value_months: int = Field(gt=0, le=240)
    risk_level: RiskLevel = "medium"
    status: InvestmentStatus = "proposed"
    committed_capital: float = Field(default=0, ge=0)
    realized_value: float = Field(default=0, ge=0)
    dependencies: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_capital(self) -> "BusinessCase":
        if self.committed_capital > self.requested_capital:
            raise ValueError("Committed capital cannot exceed requested capital")
        if self.investment_id in self.dependencies:
            raise ValueError("Investment cannot depend on itself")
        return self


class CapitalScenario(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    available_capital: float = Field(gt=0)
    risk_tolerance: float = Field(default=50, ge=0, le=100)
    minimum_alignment: float = Field(default=0, ge=0, le=100)


class CapitalPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=160)
    fiscal_period: str = Field(min_length=1, max_length=40)
    total_capital: float = Field(gt=0)
    reserve_ratio: float = Field(default=0.1, ge=0, le=0.8)
    strategy_plan_id: UUID | None = None
    transformation_portfolio_id: UUID | None = None
    resilience_plan_id: UUID | None = None
    investments: list[BusinessCase] = Field(min_length=1)
    scenarios: list[CapitalScenario] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_investments(self) -> "CapitalPortfolioCreate":
        ids = [item.investment_id for item in self.investments]
        if len(ids) != len(set(ids)):
            raise ValueError("Investment IDs must be unique")
        known = set(ids)
        for item in self.investments:
            unknown = set(item.dependencies) - known
            if unknown:
                raise ValueError("Investment dependency references unknown investment")
        return self


class AllocationUpdate(BaseModel):
    investment_id: UUID
    committed_capital: float = Field(ge=0)
    status: InvestmentStatus | None = None
    realized_value: float | None = Field(default=None, ge=0)
    actor_id: str = Field(min_length=1, max_length=100)


class InvestmentAssessment(BaseModel):
    investment_id: UUID
    priority_score: float
    risk_adjusted_value: float
    value_multiple: float
    funding_gap: float
    classification: Literal["fund", "conditional", "defer", "stop"]


class CapitalAssessment(BaseModel):
    deployable_capital: float
    committed_capital: float
    reserve_capital: float
    expected_portfolio_value: float
    realized_value: float
    capital_efficiency: float
    concentration_risk: float
    value_at_risk: float
    investment_assessments: list[InvestmentAssessment]
    recommended_funding_order: list[UUID]
    executive_recommendations: list[str]
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutiveCapitalPortfolio(BaseModel):
    portfolio_id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    name: str
    fiscal_period: str
    total_capital: float
    reserve_ratio: float
    strategy_plan_id: UUID | None = None
    transformation_portfolio_id: UUID | None = None
    resilience_plan_id: UUID | None = None
    investments: list[BusinessCase]
    scenarios: list[CapitalScenario]
    assessment: CapitalAssessment | None = None
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CapitalListResponse(BaseModel):
    items: list[ExecutiveCapitalPortfolio]
    count: int


class CapitalStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    total_capital: float
    committed_capital: float
    realized_value: float
    at_risk_investments: int
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    audit_id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    entity_id: UUID
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
