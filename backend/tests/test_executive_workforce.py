import pytest

from app.executive_workforce.models import TalentRiskUpdate, WorkforcePortfolioCreate
from app.executive_workforce.service import ExecutiveWorkforceService


def payload(workspace_id: str = "ws-1") -> WorkforcePortfolioCreate:
    return WorkforcePortfolioCreate.model_validate({
        "workspace_id": workspace_id,
        "name": "Global Workforce",
        "executive_owner_id": "chief-people-officer",
        "segments": [{
            "segment_id": "engineering",
            "name": "Engineering",
            "headcount": 120,
            "criticality": "critical",
            "capacity_utilization": 1.05,
            "engagement_score": 68,
            "retention_risk": 0.62,
            "skill_coverage": 0.64,
            "succession_coverage": 0.35,
            "vacancy_rate": 0.18,
        }],
        "critical_roles": [{
            "role_id": "principal-engineer",
            "name": "Principal Engineer",
            "segment_id": "engineering",
            "incumbents": 2,
            "required_incumbents": 4,
            "ready_successors": 0,
            "time_to_fill_days": 140,
            "business_impact": 0.9,
            "attrition_risk": 0.55,
        }],
        "risks": [{
            "risk_id": "engineering-attrition",
            "title": "Critical engineering attrition",
            "severity": 0.9,
            "probability": 0.7,
            "affected_segment_ids": ["engineering"],
            "remediation_progress": 0.1,
        }],
    })


def test_assessment_detects_critical_exposure() -> None:
    service = ExecutiveWorkforceService()
    portfolio = service.create(payload())
    assessed = service.assess(portfolio.id, "ws-1", "ceo")
    assert assessed.assessment is not None
    assert "engineering" in assessed.assessment.critical_segments
    assert "principal-engineer" in assessed.assessment.vulnerable_roles
    assert "engineering-attrition" in assessed.assessment.priority_risks
    assert assessed.assessment.executive_actions


def test_risk_update_and_workspace_isolation() -> None:
    service = ExecutiveWorkforceService()
    portfolio = service.create(payload())
    updated = service.update_risk(portfolio.id, "ws-1", TalentRiskUpdate(
        risk_id="engineering-attrition", remediation_progress=0.8, actor_id="cpo"
    ))
    assert updated.risks[0].remediation_progress == 0.8
    assert service.get(portfolio.id, "other") is None


def test_duplicate_portfolio_rejected() -> None:
    service = ExecutiveWorkforceService()
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())


def test_unknown_role_segment_rejected() -> None:
    data = payload().model_dump()
    data["critical_roles"][0]["segment_id"] = "missing"
    with pytest.raises(ValueError):
        WorkforcePortfolioCreate.model_validate(data)
