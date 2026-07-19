from copy import deepcopy
from statistics import mean
from uuid import UUID

from .models import (
    AuditRecord,
    DigitalVenturePortfolioCreate,
    DigitalVentureStatusResponse,
    ExecutiveDigitalVenturePortfolio,
    VentureRiskUpdate,
    utcnow,
)


def avg(values: list[float]) -> float:
    return round(mean(values), 2) if values else 0.0


def clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


class ExecutiveDigitalVentureService:
    def __init__(self) -> None:
        self._items: dict[UUID, ExecutiveDigitalVenturePortfolio] = {}
        self._audit: list[AuditRecord] = []

    def status(self, workspace_id: str) -> DigitalVentureStatusResponse:
        return DigitalVentureStatusResponse(
            workspace_id=workspace_id,
            portfolio_count=len(self.list_portfolios(workspace_id)),
        )

    def create(self, payload: DigitalVenturePortfolioCreate) -> ExecutiveDigitalVenturePortfolio:
        if any(i.workspace_id == payload.workspace_id and i.name.lower() == payload.name.lower() for i in self._items.values()):
            raise ValueError("Executive digital venture portfolio already exists")
        item = ExecutiveDigitalVenturePortfolio(**payload.model_dump())
        self._items[item.portfolio_id] = item
        self._audit.append(AuditRecord(workspace_id=item.workspace_id, portfolio_id=item.portfolio_id, actor_id=item.owner_id, action="portfolio.created"))
        return deepcopy(item)

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveDigitalVenturePortfolio]:
        return [deepcopy(i) for i in self._items.values() if i.workspace_id == workspace_id]

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveDigitalVenturePortfolio | None:
        item = self._items.get(portfolio_id)
        return deepcopy(item) if item and item.workspace_id == workspace_id else None

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveDigitalVenturePortfolio:
        item = self._require(portfolio_id, workspace_id)
        a = item.assessment
        a.opportunity_score = avg([
            clamp(n.demand_score * .3 + (100 - n.competition_score) * .2 + n.monetization_score * .25 + n.content_depth_score * .15 + n.trend_durability_score * .1)
            for n in item.niches
        ])
        a.offer_quality_score = avg([
            clamp(o.conversion_rate_pct * 8 + o.commission_rate_pct * .35 + o.policy_fit_score * .35 + (100 - o.refund_rate_pct * 5) * .15)
            for o in item.offers
        ])
        a.channel_health_score = avg([
            clamp(c.engagement_rate_pct * 8 + c.click_through_rate_pct * 8 + c.content_consistency_score * .45 + (100 - c.platform_dependency_score) * .25)
            for c in item.channels
        ])
        roas_scores = []
        for f in item.funnels:
            cost = f.ad_spend + f.content_cost
            roas = (f.revenue / cost) if cost else 0
            conversion = (f.conversions / f.visitors * 100) if f.visitors else 0
            roas_scores.append(clamp(roas * 20 + conversion * 10))
        a.funnel_economics_score = avg(roas_scores)
        unique_platforms = len({c.platform for c in item.channels})
        unique_offers = len({o.network for o in item.offers})
        a.diversification_score = clamp(unique_platforms * 18 + unique_offers * 12)
        a.compliance_readiness_score = avg([100 - n.compliance_risk_score for n in item.niches] + [o.policy_fit_score for o in item.offers])
        open_risks = [r for r in item.risks if r.status != "closed"]
        a.risk_exposure_score = avg([r.severity * r.probability / 100 * (1 - r.remediation_progress / 100) for r in open_risks])
        a.priority_niche_ids = [n.niche_id for n in item.niches if n.demand_score >= 65 and n.monetization_score >= 60 and n.compliance_risk_score <= 45]
        a.priority_risk_ids = [r.risk_id for r in open_risks if r.severity * r.probability / 100 >= 45]
        recs: list[str] = []
        if a.opportunity_score < 60: recs.append("Validate narrower niches before building pages or paid acquisition.")
        if a.offer_quality_score < 60: recs.append("Replace weak offers and verify commission, refund and policy economics.")
        if a.channel_health_score < 60: recs.append("Improve content cadence, hooks and channel-to-funnel alignment.")
        if a.funnel_economics_score < 55: recs.append("Do not scale ads until tracking, conversion and contribution margin improve.")
        if a.diversification_score < 50: recs.append("Reduce dependence on one platform, account or affiliate network.")
        if a.compliance_readiness_score < 70: recs.append("Strengthen disclosures, claims review and platform-policy controls.")
        if a.priority_risk_ids: recs.append("Resolve priority venture risks before autonomous execution is enabled.")
        a.recommendations = recs or ["Maintain controlled experiments and scale only proven unit economics."]
        item.updated_at = utcnow()
        self._audit.append(AuditRecord(workspace_id=workspace_id, portfolio_id=portfolio_id, actor_id=actor_id, action="portfolio.assessed"))
        return deepcopy(item)

    def update_risk(self, portfolio_id: UUID, workspace_id: str, payload: VentureRiskUpdate) -> ExecutiveDigitalVenturePortfolio:
        item = self._require(portfolio_id, workspace_id)
        risk = next((r for r in item.risks if r.risk_id == payload.risk_id), None)
        if risk is None:
            raise KeyError("Digital venture risk not found")
        risk.remediation_progress = payload.remediation_progress
        risk.status = payload.status
        item.updated_at = utcnow()
        self._audit.append(AuditRecord(workspace_id=workspace_id, portfolio_id=portfolio_id, actor_id=payload.actor_id, action="risk.updated"))
        return deepcopy(item)

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [deepcopy(a) for a in self._audit if a.workspace_id == workspace_id]

    def _require(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveDigitalVenturePortfolio:
        item = self._items.get(portfolio_id)
        if item is None or item.workspace_id != workspace_id:
            raise KeyError("Executive digital venture portfolio not found")
        return item


executive_digital_venture_service = ExecutiveDigitalVentureService()
