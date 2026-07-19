from app.executive_data_ai.models import DataAIPortfolioCreate, GovernanceUpdate
from app.executive_data_ai.service import ExecutiveDataAIService


def payload(workspace_id: str = "ws-1") -> DataAIPortfolioCreate:
    return DataAIPortfolioCreate(
        workspace_id=workspace_id,
        name="Enterprise Data and AI",
        actor_id="ceo",
        data_products=[
            {
                "data_product_id": "dp-1",
                "name": "Customer 360",
                "owner_id": "cdo",
                "business_criticality": 90,
                "quality_score": 62,
                "lineage_coverage": 70,
                "access_control_score": 85,
                "privacy_risk": 68,
            }
        ],
        ai_systems=[
            {
                "ai_system_id": "ai-1",
                "name": "Decision Copilot",
                "owner_id": "cto",
                "risk_level": "high",
                "business_impact": 90,
                "model_performance": 82,
                "explainability": 55,
                "human_oversight": 60,
                "compliance_readiness": 58,
                "bias_risk": 48,
                "drift_risk": 42,
            }
        ],
        issues=[
            {
                "issue_id": "issue-1",
                "asset_id": "ai-1",
                "severity": 80,
                "remediation_progress": 20,
                "description": "Human oversight controls incomplete",
            }
        ],
    )


def test_assessment_identifies_critical_assets_and_risk():
    service = ExecutiveDataAIService()
    item = service.create(payload())
    assessed = service.assess(item.portfolio_id, "ws-1", "ceo")
    assert "dp-1" in assessed.critical_data_products
    assert "ai-1" in assessed.high_risk_ai_systems
    assert assessed.compliance_exposure > 0
    assert assessed.autonomous_actions_enabled is False


def test_workspace_isolation_and_issue_update():
    service = ExecutiveDataAIService()
    item = service.create(payload())
    assert service.get(item.portfolio_id, "other") is None
    updated = service.update_issue(
        item.portfolio_id,
        "ws-1",
        GovernanceUpdate(actor_id="risk", issue_id="issue-1", remediation_progress=75),
    )
    assert updated.issues[0].remediation_progress == 75


def test_duplicate_portfolio_rejected():
    service = ExecutiveDataAIService()
    service.create(payload())
    try:
        service.create(payload())
        assert False
    except ValueError:
        assert True
