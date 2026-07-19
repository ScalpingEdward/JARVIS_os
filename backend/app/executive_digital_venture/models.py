from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NicheOpportunity(BaseModel):
    niche_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=160)
    demand_score: float = Field(ge=0, le=100)
    competition_score: float = Field(ge=0, le=100)
    monetization_score: float = Field(ge=0, le=100)
    content_depth_score: float = Field(ge=0, le=100)
    compliance_risk_score: float = Field(ge=0, le=100)
    trend_durability_score: float = Field(ge=0, le=100)


class AffiliateOffer(BaseModel):
    offer_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=160)
    network: str = Field(min_length=1, max_length=120)
    commission_rate_pct: float = Field(ge=0, le=100)
    average_order_value: float = Field(ge=0)
    conversion_rate_pct: float = Field(ge=0, le=100)
    refund_rate_pct: float = Field(ge=0, le=100)
    cookie_days: int = Field(ge=0, le=3650)
    policy_fit_score: float = Field(ge=0, le=100)


class GrowthChannel(BaseModel):
    channel_id: UUID = Field(default_factory=uuid4)
    platform: Literal["instagram", "youtube", "tiktok", "website", "email", "paid_social", "search"]
    account_name: str = Field(min_length=1, max_length=160)
    faceless: bool = True
    monthly_reach: int = Field(ge=0)
    engagement_rate_pct: float = Field(ge=0, le=100)
    click_through_rate_pct: float = Field(ge=0, le=100)
    content_consistency_score: float = Field(ge=0, le=100)
    platform_dependency_score: float = Field(ge=0, le=100)


class FunnelMetric(BaseModel):
    funnel_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=160)
    visitors: int = Field(ge=0)
    leads: int = Field(ge=0)
    conversions: int = Field(ge=0)
    revenue: float = Field(ge=0)
    ad_spend: float = Field(ge=0)
    content_cost: float = Field(ge=0)


class VentureRisk(BaseModel):
    risk_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=160)
    category: Literal["platform", "offer", "compliance", "content", "tracking", "reputation", "economics"]
    severity: float = Field(ge=0, le=100)
    probability: float = Field(ge=0, le=100)
    remediation_progress: float = Field(ge=0, le=100)
    status: Literal["open", "mitigating", "accepted", "closed"] = "open"


class VentureRiskUpdate(BaseModel):
    risk_id: UUID
    remediation_progress: float = Field(ge=0, le=100)
    status: Literal["open", "mitigating", "accepted", "closed"]
    actor_id: str = Field(min_length=1, max_length=100)


class DigitalVentureAssessment(BaseModel):
    opportunity_score: float = 0
    offer_quality_score: float = 0
    channel_health_score: float = 0
    funnel_economics_score: float = 0
    diversification_score: float = 0
    compliance_readiness_score: float = 0
    risk_exposure_score: float = 0
    priority_niche_ids: list[UUID] = Field(default_factory=list)
    priority_risk_ids: list[UUID] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class DigitalVenturePortfolioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=160)
    owner_id: str = Field(min_length=1, max_length=100)
    monthly_budget: float = Field(ge=0)
    niches: list[NicheOpportunity] = Field(default_factory=list)
    offers: list[AffiliateOffer] = Field(default_factory=list)
    channels: list[GrowthChannel] = Field(default_factory=list)
    funnels: list[FunnelMetric] = Field(default_factory=list)
    risks: list[VentureRisk] = Field(default_factory=list)
    strategy_portfolio_id: UUID | None = None
    reputation_portfolio_id: UUID | None = None
    customer_portfolio_id: UUID | None = None

    @model_validator(mode="after")
    def validate_unique_ids(self):
        groups = [self.niches, self.offers, self.channels, self.funnels, self.risks]
        for group in groups:
            ids = [next(v for k, v in item.model_dump().items() if k.endswith("_id")) for item in group]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate identifiers are not allowed")
        return self


class ExecutiveDigitalVenturePortfolio(DigitalVenturePortfolioCreate):
    portfolio_id: UUID = Field(default_factory=uuid4)
    assessment: DigitalVentureAssessment = Field(default_factory=DigitalVentureAssessment)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class DigitalVentureStatusResponse(BaseModel):
    workspace_id: str
    portfolio_count: int
    autonomous_execution_enabled: bool = False


class DigitalVentureListResponse(BaseModel):
    items: list[ExecutiveDigitalVenturePortfolio]
    count: int


class AuditRecord(BaseModel):
    audit_id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    portfolio_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=utcnow)
