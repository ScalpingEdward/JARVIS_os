from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class CashPosition(BaseModel):
    position_id: str = Field(min_length=1, max_length=100)
    entity: str = Field(min_length=1, max_length=160)
    currency: str = Field(min_length=3, max_length=3)
    available_cash: float = Field(ge=0)
    restricted_cash: float = Field(default=0, ge=0)
    forecast_accuracy_score: float = Field(ge=0, le=100)
    concentration_score: float = Field(ge=0, le=100)


class FundingSource(BaseModel):
    source_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=180)
    committed_amount: float = Field(ge=0)
    drawn_amount: float = Field(ge=0)
    maturity_months: int = Field(ge=0)
    interest_rate_percent: float = Field(ge=0)
    covenant_headroom_score: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_drawn_amount(self) -> "FundingSource":
        if self.drawn_amount > self.committed_amount:
            raise ValueError("Drawn amount cannot exceed committed amount")
        return self


class TreasuryRisk(BaseModel):
    risk_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=240)
    severity: Severity
    probability: float = Field(ge=0, le=1)
    impact_score: float = Field(ge=0, le=100)
    risk_type: str = Field(min_length=1, max_length=100)
    remediation_progress: float = Field(default=0, ge=0, le=100)


class StressScenario(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=180)
    cash_outflow_percent: float = Field(ge=0, le=100)
    funding_reduction_percent: float = Field(ge=0, le=100)
    fx_shock_percent: float = Field(ge=0, le=100)
    survival_months: float = Field(ge=0)
    response_readiness_score: float = Field(ge=0, le=100)


class TreasuryPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    executive_owner_id: str = Field(min_length=1, max_length=100)
    strategy_portfolio_id: UUID | None = None
    capital_portfolio_id: UUID | None = None
    geopolitical_portfolio_id: UUID | None = None
    cash_positions: list[CashPosition] = Field(min_length=1)
    funding_sources: list[FundingSource] = Field(default_factory=list)
    risks: list[TreasuryRisk] = Field(default_factory=list)
    stress_scenarios: list[StressScenario] = Field(default_factory=list)
    fx_hedge_coverage_score: float = Field(ge=0, le=100)
    interest_rate_hedge_coverage_score: float = Field(ge=0, le=100)
    counterparty_diversification_score: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "TreasuryPortfolioCreate":
        groups = [
            ("cash position", [item.position_id for item in self.cash_positions]),
            ("funding source", [item.source_id for item in self.funding_sources]),
            ("treasury risk", [item.risk_id for item in self.risks]),
            ("stress scenario", [item.scenario_id for item in self.stress_scenarios]),
        ]
        for label, values in groups:
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate {label} IDs are not allowed")
        return self


class TreasuryRiskUpdate(BaseModel):
    risk_id: str = Field(min_length=1, max_length=100)
    remediation_progress: float = Field(ge=0, le=100)
    actor_id: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=1000)


class TreasuryAssessment(BaseModel):
    liquidity_health_score: float = Field(ge=0, le=100)
    funding_resilience_score: float = Field(ge=0, le=100)
    forecast_quality_score: float = Field(ge=0, le=100)
    market_risk_coverage_score: float = Field(ge=0, le=100)
    counterparty_resilience_score: float = Field(ge=0, le=100)
    stress_survival_score: float = Field(ge=0, le=100)
    risk_exposure_score: float = Field(ge=0, le=100)
    priority_risks: list[str] = Field(default_factory=list)
    vulnerable_funding_sources: list[str] = Field(default_factory=list)
    executive_actions: list[str] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutiveTreasuryPortfolio(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    name: str
    executive_owner_id: str
    strategy_portfolio_id: UUID | None = None
    capital_portfolio_id: UUID | None = None
    geopolitical_portfolio_id: UUID | None = None
    cash_positions: list[CashPosition]
    funding_sources: list[FundingSource]
    risks: list[TreasuryRisk]
    stress_scenarios: list[StressScenario]
    fx_hedge_coverage_score: float
    interest_rate_hedge_coverage_score: float
    counterparty_diversification_score: float
    assessment: TreasuryAssessment | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TreasuryStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    total_available_cash: float
    total_committed_funding: float
    open_risks: int
    critical_risks: int
    autonomous_actions_enabled: bool = False


class TreasuryListResponse(BaseModel):
    items: list[ExecutiveTreasuryPortfolio]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    resource_id: UUID
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
