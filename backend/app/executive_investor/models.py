from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class InvestorType(str, Enum):
    institutional = "institutional"
    retail = "retail"
    strategic = "strategic"
    sovereign = "sovereign"
    activist = "activist"
    debt_holder = "debt_holder"


class RiskSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class InvestorSegment(BaseModel):
    segment_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    investor_type: InvestorType
    ownership_percent: float = Field(ge=0, le=100)
    engagement_score: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=100)
    valuation_alignment_score: float = Field(ge=0, le=100)
    long_term_orientation_score: float = Field(ge=0, le=100)
    concentration_risk_score: float = Field(ge=0, le=100)


class AnalystCoverage(BaseModel):
    analyst_id: str = Field(min_length=1, max_length=100)
    firm: str = Field(min_length=1, max_length=200)
    recommendation_score: float = Field(ge=0, le=100)
    target_price_gap_percent: float = Field(ge=-100, le=300)
    model_understanding_score: float = Field(ge=0, le=100)
    access_quality_score: float = Field(ge=0, le=100)
    estimate_dispersion_score: float = Field(ge=0, le=100)


class GuidanceMetric(BaseModel):
    metric_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    guidance_accuracy_score: float = Field(ge=0, le=100)
    consensus_gap_percent: float = Field(ge=-100, le=100)
    disclosure_clarity_score: float = Field(ge=0, le=100)
    controllability_score: float = Field(ge=0, le=100)


class CapitalMarketsRisk(BaseModel):
    risk_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=240)
    severity: RiskSeverity
    probability: float = Field(ge=0, le=1)
    impact_score: float = Field(ge=0, le=100)
    affected_segment_ids: list[str] = Field(default_factory=list)
    remediation_progress: float = Field(default=0, ge=0, le=100)
    response_readiness_score: float = Field(default=0, ge=0, le=100)


class InvestorPortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    executive_owner_id: str = Field(min_length=1, max_length=100)
    strategy_portfolio_id: UUID | None = None
    treasury_portfolio_id: UUID | None = None
    reputation_portfolio_id: UUID | None = None
    board_portfolio_id: UUID | None = None
    investor_segments: list[InvestorSegment] = Field(min_length=1)
    analyst_coverage: list[AnalystCoverage] = Field(default_factory=list)
    guidance_metrics: list[GuidanceMetric] = Field(default_factory=list)
    risks: list[CapitalMarketsRisk] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "InvestorPortfolioCreate":
        segment_ids = [item.segment_id for item in self.investor_segments]
        if len(segment_ids) != len(set(segment_ids)):
            raise ValueError("Duplicate investor segment IDs are not allowed")
        analyst_ids = [item.analyst_id for item in self.analyst_coverage]
        if len(analyst_ids) != len(set(analyst_ids)):
            raise ValueError("Duplicate analyst IDs are not allowed")
        metric_ids = [item.metric_id for item in self.guidance_metrics]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("Duplicate guidance metric IDs are not allowed")
        risk_ids = [item.risk_id for item in self.risks]
        if len(risk_ids) != len(set(risk_ids)):
            raise ValueError("Duplicate capital-markets risk IDs are not allowed")
        known_segments = set(segment_ids)
        for risk in self.risks:
            missing = set(risk.affected_segment_ids) - known_segments
            if missing:
                raise ValueError(f"Unknown investor segments: {sorted(missing)}")
        if sum(item.ownership_percent for item in self.investor_segments) > 100.01:
            raise ValueError("Investor segment ownership cannot exceed 100 percent")
        return self


class CapitalMarketsRiskUpdate(BaseModel):
    risk_id: str = Field(min_length=1, max_length=100)
    remediation_progress: float = Field(ge=0, le=100)
    response_readiness_score: float | None = Field(default=None, ge=0, le=100)
    actor_id: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=1000)


class InvestorAssessment(BaseModel):
    investor_confidence_score: float = Field(ge=0, le=100)
    engagement_quality_score: float = Field(ge=0, le=100)
    valuation_alignment_score: float = Field(ge=0, le=100)
    guidance_credibility_score: float = Field(ge=0, le=100)
    analyst_understanding_score: float = Field(ge=0, le=100)
    ownership_resilience_score: float = Field(ge=0, le=100)
    capital_markets_risk_score: float = Field(ge=0, le=100)
    vulnerable_segments: list[str] = Field(default_factory=list)
    priority_risks: list[str] = Field(default_factory=list)
    executive_actions: list[str] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutiveInvestorPortfolio(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    name: str
    executive_owner_id: str
    strategy_portfolio_id: UUID | None = None
    treasury_portfolio_id: UUID | None = None
    reputation_portfolio_id: UUID | None = None
    board_portfolio_id: UUID | None = None
    investor_segments: list[InvestorSegment]
    analyst_coverage: list[AnalystCoverage]
    guidance_metrics: list[GuidanceMetric]
    risks: list[CapitalMarketsRisk]
    assessment: InvestorAssessment | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InvestorStatusResponse(BaseModel):
    workspace_id: str
    portfolios: int
    investor_segments: int
    analysts: int
    open_risks: int
    critical_risks: int
    autonomous_actions_enabled: bool = False


class InvestorListResponse(BaseModel):
    items: list[ExecutiveInvestorPortfolio]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    resource_id: UUID
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
