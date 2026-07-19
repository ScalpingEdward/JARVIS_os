import pytest
from pydantic import ValidationError

from app.executive_ma.models import IntegrationRiskUpdate, MAPortfolioCreate
from app.executive_ma.service import ExecutiveMAService


def payload(workspace_id: str = "ws-1", name: str = "Acquisition Alpha") -> MAPortfolioCreate:
    return MAPortfolioCreate(
        workspace_id=workspace_id,
        name=name,
        executive_owner_id="exec-1",
        deal_stage="integration",
        purchase_price=250_000_000,
        strategic_fit_score=85,
        culture_alignment_score=58,
        talent_retention_score=62,
        customer_continuity_score=72,
        workstreams=[
            {
                "workstream_id": "technology",
                "name": "Technology integration",
                "owner_id": "cto-1",
                "progress": 45,
                "day_1_readiness": 78,
                "day_100_readiness": 52,
                "dependency_risk": 72,
                "tsa_dependency": 80,
            },
            {
                "workstream_id": "commercial",
                "name": "Commercial integration",
                "owner_id": "cro-1",
                "progress": 75,
                "day_1_readiness": 88,
                "day_100_readiness": 74,
                "dependency_risk": 35,
                "tsa_dependency": 20,
            },
        ],
        synergies=[
            {
                "synergy_id": "cost-1",
                "name": "Platform consolidation",
                "target_value": 20_000_000,
                "realized_value": 5_000_000,
                "confidence_score": 60,
                "timing_readiness": 55,
            }
        ],
        risks=[
            {
                "risk_id": "talent-loss",
                "title": "Critical engineering talent loss",
                "severity": "critical",
                "probability": 0.8,
                "impact_score": 90,
                "remediation_progress": 20,
            }
        ],
    )


def test_assessment_detects_value_leakage_and_priority_items() -> None:
    service = ExecutiveMAService()
    item = service.create(payload())
    assessed = service.assess(item.id, "ws-1", "exec-1")
    assert assessed.assessment is not None
    assert "technology" in assessed.assessment.priority_workstreams
    assert "talent-loss" in assessed.assessment.priority_risks
    assert assessed.assessment.value_leakage_exposure > 0


def test_risk_update_and_workspace_isolation() -> None:
    service = ExecutiveMAService()
    item = service.create(payload())
    updated = service.update_risk(item.id, "ws-1", IntegrationRiskUpdate(risk_id="talent-loss", remediation_progress=85, actor_id="exec-2"))
    assert updated.risks[0].remediation_progress == 85
    assert service.get(item.id, "other-workspace") is None
    assert len(service.audit_records("ws-1")) == 2


def test_duplicate_portfolio_is_rejected() -> None:
    service = ExecutiveMAService()
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())


def test_duplicate_workstream_ids_are_rejected() -> None:
    data = payload().model_dump()
    data["workstreams"].append(data["workstreams"][0])
    with pytest.raises(ValidationError):
        MAPortfolioCreate(**data)
