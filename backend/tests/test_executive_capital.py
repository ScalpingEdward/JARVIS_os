from uuid import uuid4

import pytest

from app.executive_capital.models import AllocationUpdate, BusinessCase, CapitalPortfolioCreate
from app.executive_capital.service import ExecutiveCapitalService


def _payload(workspace_id: str = "ws-1") -> CapitalPortfolioCreate:
    first_id = uuid4()
    return CapitalPortfolioCreate(
        workspace_id=workspace_id,
        name="FY27 Strategic Capital",
        fiscal_period="FY27",
        total_capital=1_000_000,
        reserve_ratio=0.1,
        investments=[
            BusinessCase(
                investment_id=first_id,
                name="AI Operations Platform",
                owner_id="cto",
                requested_capital=300_000,
                expected_value=900_000,
                probability_of_success=0.75,
                strategic_alignment=92,
                time_to_value_months=12,
                risk_level="medium",
            ),
            BusinessCase(
                name="Legacy Expansion",
                owner_id="coo",
                requested_capital=500_000,
                expected_value=180_000,
                probability_of_success=0.4,
                strategic_alignment=35,
                time_to_value_months=36,
                risk_level="high",
                dependencies=[first_id],
            ),
        ],
    )


def test_assessment_prioritizes_value_and_flags_weak_case() -> None:
    service = ExecutiveCapitalService()
    portfolio = service.create(_payload())
    assessed = service.assess(portfolio.portfolio_id, "ws-1", "cfo")
    assert assessed.assessment is not None
    assessments = {item.investment_id: item for item in assessed.assessment.investment_assessments}
    assert assessments[portfolio.investments[0].investment_id].classification == "fund"
    assert assessments[portfolio.investments[1].investment_id].classification in {"defer", "stop"}
    assert assessed.assessment.recommended_funding_order[0] == portfolio.investments[0].investment_id
    assert assessed.autonomous_actions_enabled is False


def test_allocation_update_invalidates_assessment() -> None:
    service = ExecutiveCapitalService()
    portfolio = service.create(_payload())
    service.assess(portfolio.portfolio_id, "ws-1", "cfo")
    updated = service.update_allocation(
        portfolio.portfolio_id,
        "ws-1",
        AllocationUpdate(
            investment_id=portfolio.investments[0].investment_id,
            committed_capital=200_000,
            realized_value=50_000,
            status="funded",
            actor_id="cfo",
        ),
    )
    assert updated.assessment is None
    assert updated.investments[0].committed_capital == 200_000
    assert service.status("ws-1").realized_value == 50_000


def test_workspace_isolation_and_duplicates() -> None:
    service = ExecutiveCapitalService()
    portfolio = service.create(_payload("alpha"))
    assert service.get(portfolio.portfolio_id, "beta") is None
    assert service.list_portfolios("beta") == []
    with pytest.raises(ValueError):
        service.create(_payload("alpha"))


def test_rejects_unknown_dependency() -> None:
    with pytest.raises(ValueError):
        CapitalPortfolioCreate(
            workspace_id="ws",
            name="Invalid",
            fiscal_period="FY27",
            total_capital=1000,
            investments=[
                BusinessCase(
                    name="Broken",
                    owner_id="owner",
                    requested_capital=100,
                    expected_value=200,
                    probability_of_success=0.8,
                    strategic_alignment=80,
                    time_to_value_months=4,
                    dependencies=[uuid4()],
                )
            ],
        )
