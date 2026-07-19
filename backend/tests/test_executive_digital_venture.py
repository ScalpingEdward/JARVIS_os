from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.executive_digital_venture.models import (
    AffiliateOffer,
    DigitalVenturePortfolioCreate,
    FunnelMetric,
    GrowthChannel,
    NicheOpportunity,
    VentureRisk,
    VentureRiskUpdate,
)
from app.executive_digital_venture.service import ExecutiveDigitalVentureService


def payload(workspace_id: str = "ws-a") -> DigitalVenturePortfolioCreate:
    return DigitalVenturePortfolioCreate(
        workspace_id=workspace_id,
        name="Faceless Growth Portfolio",
        owner_id="brano",
        monthly_budget=1500,
        niches=[NicheOpportunity(name="Performance tools", demand_score=82, competition_score=48, monetization_score=79, content_depth_score=88, compliance_risk_score=20, trend_durability_score=76)],
        offers=[AffiliateOffer(name="Tool subscription", network="direct", commission_rate_pct=30, average_order_value=120, conversion_rate_pct=4.5, refund_rate_pct=3, cookie_days=30, policy_fit_score=92)],
        channels=[GrowthChannel(platform="instagram", account_name="faceless-lab", monthly_reach=50000, engagement_rate_pct=5, click_through_rate_pct=2.5, content_consistency_score=84, platform_dependency_score=60)],
        funnels=[FunnelMetric(name="IG landing page", visitors=10000, leads=900, conversions=150, revenue=5400, ad_spend=1200, content_cost=600)],
        risks=[VentureRisk(name="Platform concentration", category="platform", severity=80, probability=70, remediation_progress=20)],
    )


def test_assessment_produces_priorities_and_recommendations() -> None:
    service = ExecutiveDigitalVentureService()
    item = service.create(payload())
    assessed = service.assess(item.portfolio_id, "ws-a", "brano")
    assert assessed.assessment.opportunity_score > 0
    assert assessed.assessment.offer_quality_score > 0
    assert assessed.assessment.priority_niche_ids
    assert assessed.assessment.priority_risk_ids
    assert assessed.assessment.recommendations


def test_risk_update_is_governed_and_audited() -> None:
    service = ExecutiveDigitalVentureService()
    item = service.create(payload())
    risk = item.risks[0]
    updated = service.update_risk(item.portfolio_id, "ws-a", VentureRiskUpdate(risk_id=risk.risk_id, remediation_progress=100, status="closed", actor_id="owner"))
    assert updated.risks[0].status == "closed"
    assert [a.action for a in service.audit_records("ws-a")] == ["portfolio.created", "risk.updated"]


def test_workspace_isolation_and_duplicate_name() -> None:
    service = ExecutiveDigitalVentureService()
    item = service.create(payload())
    assert service.get(item.portfolio_id, "ws-b") is None
    with pytest.raises(KeyError):
        service.assess(item.portfolio_id, "ws-b", "actor")
    with pytest.raises(ValueError):
        service.create(payload())


def test_duplicate_nested_ids_rejected() -> None:
    niche_id = uuid4()
    data = payload().model_dump()
    data["niches"] = [
        {**data["niches"][0], "niche_id": niche_id},
        {**data["niches"][0], "niche_id": niche_id, "name": "Duplicate"},
    ]
    with pytest.raises(ValidationError):
        DigitalVenturePortfolioCreate(**data)


def test_autonomous_execution_disabled() -> None:
    service = ExecutiveDigitalVentureService()
    status = service.status("ws-a")
    assert status.autonomous_execution_enabled is False
