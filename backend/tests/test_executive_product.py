from app.executive_product.models import InitiativeUpdate, ProductPortfolioCreate
from app.executive_product.service import ExecutiveProductService


def payload(workspace_id: str = "ws-1") -> ProductPortfolioCreate:
    return ProductPortfolioCreate(
        workspace_id=workspace_id,
        name="Product Portfolio",
        actor_id="ceo",
        products=[
            {
                "product_id": "p1",
                "name": "Automation Core",
                "stage": "scale",
                "annual_revenue": 1200,
                "gross_margin": 72,
                "market_fit": 88,
                "strategic_alignment": 92,
                "growth_potential": 85,
                "technical_health": 78,
            },
            {
                "product_id": "p2",
                "name": "Legacy Console",
                "stage": "mature",
                "annual_revenue": 400,
                "gross_margin": 35,
                "market_fit": 45,
                "strategic_alignment": 40,
                "growth_potential": 25,
                "technical_health": 35,
            },
        ],
        initiatives=[
            {
                "initiative_id": "i1",
                "name": "Agentic Workspace",
                "owner_id": "cto",
                "investment_required": 250,
                "expected_annual_value": 800,
                "time_to_market_months": 8,
                "feasibility": 80,
                "customer_desirability": 88,
                "strategic_alignment": 94,
                "execution_risk": 30,
            }
        ],
    )


def test_assessment_prioritizes_innovation_and_reviews_legacy_product():
    service = ExecutiveProductService()
    item = service.create(payload())
    assessed = service.assess(item.portfolio_id, "ws-1", "ceo")
    assert "i1" in assessed.priority_initiatives
    assert "p2" in assessed.review_products
    assert assessed.expected_innovation_value == 800
    assert assessed.autonomous_actions_enabled is False


def test_workspace_isolation_and_initiative_update():
    service = ExecutiveProductService()
    item = service.create(payload())
    assert service.get(item.portfolio_id, "other") is None
    updated = service.update_initiative(
        item.portfolio_id,
        "ws-1",
        InitiativeUpdate(actor_id="cto", initiative_id="i1", execution_risk=20),
    )
    assert updated.initiatives[0].execution_risk == 20


def test_duplicate_portfolio_rejected():
    service = ExecutiveProductService()
    service.create(payload())
    try:
        service.create(payload())
        assert False
    except ValueError:
        assert True
