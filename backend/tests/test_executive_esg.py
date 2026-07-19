import pytest
from pydantic import ValidationError

from app.executive_esg.models import EsgIssue, EsgIssueUpdate, EsgMetric, EsgPillar, EsgPortfolioCreate, SustainabilityInitiative
from app.executive_esg.service import ExecutiveEsgService


def payload(workspace_id: str = "ws-1") -> EsgPortfolioCreate:
    return EsgPortfolioCreate(
        workspace_id=workspace_id,
        name="Enterprise ESG",
        actor_id="exec-1",
        metrics=[
            EsgMetric(metric_id="carbon", name="Carbon reduction", pillar=EsgPillar.environmental, current_value=60, target_value=100, weight=40, data_quality=90, regulatory_materiality=90),
            EsgMetric(metric_id="safety", name="Workforce safety", pillar=EsgPillar.social, current_value=85, target_value=100, weight=30, data_quality=95, regulatory_materiality=80),
            EsgMetric(metric_id="ethics", name="Ethics controls", pillar=EsgPillar.governance, current_value=75, target_value=100, weight=30, data_quality=85, regulatory_materiality=85),
        ],
        initiatives=[
            SustainabilityInitiative(initiative_id="renewables", name="Renewable transition", pillar=EsgPillar.environmental, investment_required=500000, expected_annual_savings=180000, impact_score=90, execution_readiness=80, delivery_risk=30)
        ],
        issues=[EsgIssue(issue_id="reporting", pillar=EsgPillar.governance, severity=80, remediation_progress=20, description="Reporting controls incomplete")],
    )


def test_assessment_scores_and_recommendations() -> None:
    service = ExecutiveEsgService()
    item = service.create(payload())
    assessed = service.assess(item.portfolio_id, "ws-1", "exec-2")
    assert assessed.overall_esg_score > 0
    assert assessed.compliance_exposure > 0
    assert "renewables" in assessed.priority_initiatives
    assert "carbon" in assessed.material_gaps
    assert assessed.assessed_at is not None
    assert service.status("ws-1").assessed_portfolios == 1


def test_issue_update_and_audit() -> None:
    service = ExecutiveEsgService()
    item = service.create(payload())
    updated = service.update_issue(item.portfolio_id, "ws-1", EsgIssueUpdate(actor_id="exec-2", issue_id="reporting", remediation_progress=75))
    assert updated.issues[0].remediation_progress == 75
    actions = [record.action for record in service.audit_records("ws-1")]
    assert actions == ["esg_portfolio_created", "esg_issue_updated"]


def test_workspace_isolation() -> None:
    service = ExecutiveEsgService()
    item = service.create(payload("ws-a"))
    assert service.get(item.portfolio_id, "ws-b") is None
    assert service.list_portfolios("ws-b") == []


def test_duplicate_metric_ids_rejected() -> None:
    metric = EsgMetric(metric_id="same", name="Metric", pillar=EsgPillar.environmental, current_value=1, target_value=2, weight=10, data_quality=80, regulatory_materiality=70)
    with pytest.raises(ValidationError):
        EsgPortfolioCreate(workspace_id="ws", name="ESG", actor_id="exec", metrics=[metric, metric])
