from app.executive_customer.models import CustomerPortfolioCreate, CustomerSignalUpdate
from app.executive_customer.service import ExecutiveCustomerService


def payload(workspace_id: str = "ws-1") -> CustomerPortfolioCreate:
    return CustomerPortfolioCreate(
        workspace_id=workspace_id,
        name="Customer Growth Portfolio",
        actor_id="cro",
        segments=[
            {
                "segment_id": "enterprise",
                "name": "Enterprise",
                "customers": 50,
                "annual_revenue": 1_000_000,
                "gross_margin": 75,
                "retention_rate": 92,
                "expansion_rate": 18,
                "acquisition_cost": 10_000,
                "lifetime_value": 120_000,
                "strategic_importance": 90,
            },
            {
                "segment_id": "smb",
                "name": "SMB",
                "customers": 500,
                "annual_revenue": 500_000,
                "gross_margin": 55,
                "retention_rate": 72,
                "expansion_rate": 2,
                "acquisition_cost": 1_000,
                "lifetime_value": 4_000,
                "strategic_importance": 55,
            },
        ],
        signals=[
            {
                "signal_id": "sig-smb",
                "segment_id": "smb",
                "churn_probability": 70,
                "revenue_at_risk": 120_000,
                "satisfaction_score": 45,
                "description": "Service complaints increased",
            }
        ],
    )


def test_assessment_identifies_growth_and_vulnerability():
    service = ExecutiveCustomerService()
    item = service.create(payload())
    assessed = service.assess(item.portfolio_id, "ws-1", "cro")
    assert "enterprise" in assessed.expansion_segments
    assert "smb" in assessed.vulnerable_segments
    assert assessed.total_revenue == 1_500_000
    assert assessed.revenue_at_risk == 120_000
    assert assessed.autonomous_actions_enabled is False


def test_workspace_isolation_and_signal_update():
    service = ExecutiveCustomerService()
    item = service.create(payload())
    assert service.get(item.portfolio_id, "other") is None
    updated = service.update_signal(
        item.portfolio_id,
        "ws-1",
        CustomerSignalUpdate(actor_id="analyst", signal_id="sig-smb", churn_probability=50),
    )
    assert updated.signals[0].churn_probability == 50


def test_duplicate_and_unknown_segment_validation():
    service = ExecutiveCustomerService()
    service.create(payload())
    try:
        service.create(payload())
        assert False
    except ValueError:
        assert True

    try:
        CustomerPortfolioCreate(
            workspace_id="ws-2",
            name="Invalid",
            actor_id="cro",
            segments=[payload().segments[0]],
            signals=[
                {
                    "signal_id": "x",
                    "segment_id": "missing",
                    "churn_probability": 10,
                    "revenue_at_risk": 0,
                    "satisfaction_score": 90,
                    "description": "Invalid reference",
                }
            ],
        )
        assert False
    except ValueError:
        assert True
