import pytest
from pydantic import ValidationError

from app.executive_investor.models import CapitalMarketsRiskUpdate, InvestorPortfolioCreate
from app.executive_investor.service import ExecutiveInvestorService


def payload(workspace_id: str = "ws-1", name: str = "Capital markets") -> InvestorPortfolioCreate:
    return InvestorPortfolioCreate(
        workspace_id=workspace_id,
        name=name,
        executive_owner_id="exec-1",
        investor_segments=[
            {
                "segment_id": "long-only",
                "name": "Long-only institutions",
                "investor_type": "institutional",
                "ownership_percent": 48,
                "engagement_score": 52,
                "confidence_score": 55,
                "valuation_alignment_score": 50,
                "long_term_orientation_score": 85,
                "concentration_risk_score": 35,
            },
            {
                "segment_id": "activists",
                "name": "Activist investors",
                "investor_type": "activist",
                "ownership_percent": 8,
                "engagement_score": 75,
                "confidence_score": 42,
                "valuation_alignment_score": 40,
                "long_term_orientation_score": 35,
                "concentration_risk_score": 80,
            },
        ],
        analyst_coverage=[
            {
                "analyst_id": "analyst-1",
                "firm": "Example Securities",
                "recommendation_score": 60,
                "target_price_gap_percent": -18,
                "model_understanding_score": 55,
                "access_quality_score": 65,
                "estimate_dispersion_score": 45,
            }
        ],
        guidance_metrics=[
            {
                "metric_id": "revenue",
                "name": "Revenue growth",
                "guidance_accuracy_score": 58,
                "consensus_gap_percent": -12,
                "disclosure_clarity_score": 62,
                "controllability_score": 70,
            }
        ],
        risks=[
            {
                "risk_id": "guidance-reset",
                "title": "Potential guidance reset",
                "severity": "critical",
                "probability": 0.8,
                "impact_score": 90,
                "affected_segment_ids": ["long-only", "activists"],
                "remediation_progress": 20,
                "response_readiness_score": 45,
            }
        ],
    )


def test_assessment_detects_vulnerable_segments_and_priority_risks() -> None:
    service = ExecutiveInvestorService()
    item = service.create(payload())
    assessed = service.assess(item.id, "ws-1", "exec-1")
    assert assessed.assessment is not None
    assert "activists" in assessed.assessment.vulnerable_segments
    assert "guidance-reset" in assessed.assessment.priority_risks
    assert assessed.assessment.capital_markets_risk_score > 0


def test_risk_update_and_workspace_isolation() -> None:
    service = ExecutiveInvestorService()
    item = service.create(payload())
    updated = service.update_risk(
        item.id,
        "ws-1",
        CapitalMarketsRiskUpdate(
            risk_id="guidance-reset",
            remediation_progress=85,
            response_readiness_score=80,
            actor_id="exec-2",
        ),
    )
    assert updated.risks[0].remediation_progress == 85
    assert service.get(item.id, "other-workspace") is None
    assert len(service.audit_records("ws-1")) == 2


def test_duplicate_portfolio_is_rejected() -> None:
    service = ExecutiveInvestorService()
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())


def test_unknown_segment_and_excess_ownership_are_rejected() -> None:
    data = payload().model_dump()
    data["risks"][0]["affected_segment_ids"] = ["unknown"]
    with pytest.raises(ValidationError):
        InvestorPortfolioCreate(**data)

    data = payload().model_dump()
    data["investor_segments"][0]["ownership_percent"] = 95
    with pytest.raises(ValidationError):
        InvestorPortfolioCreate(**data)
