import pytest

from app.executive_multi_account_portfolio_manager.models import AccountAllocationInput, MultiAccountAllocationCreate, MultiAccountAllocationExecuteRequest, MultiAccountPortfolioState
from app.executive_multi_account_portfolio_manager.service import MultiAccountPortfolioManagerService


def payload(**changes):
    data = dict(
        workspace_id="ws-a", source_key="allocation-1", actor_id="tester",
        portfolio_risk_approved=True, requested_total_risk=1000, max_portfolio_risk=5000,
        accounts=[
            AccountAllocationInput(account_id="a1", broker="b1", balance=100000, equity=101000, current_risk=500, max_risk=2500, health_score=90, correlation_score=0.1, prop_rules_approved=True, account_risk_approved=True),
            AccountAllocationInput(account_id="a2", broker="b2", balance=50000, equity=49500, current_risk=200, max_risk=1500, health_score=80, correlation_score=0.2, prop_rules_approved=True, account_risk_approved=True),
        ],
    )
    data.update(changes)
    return MultiAccountAllocationCreate(**data)


def test_allocation_and_activation():
    service = MultiAccountPortfolioManagerService()
    record = service.create(payload())
    assert record.allocated_total_risk > 0
    assert sum(item.allocated_risk for item in record.allocations) == record.allocated_total_risk
    activated = service.execute(record.id, "ws-a", MultiAccountAllocationExecuteRequest(actor_id="approver", human_approved=True))
    assert activated.state == MultiAccountPortfolioState.ALLOCATION_APPROVED


def test_requires_portfolio_risk_approval():
    service = MultiAccountPortfolioManagerService()
    record = service.create(payload(portfolio_risk_approved=False))
    assert record.state == MultiAccountPortfolioState.PORTFOLIO_STATE_REQUIRED


def test_upstream_risk_block_fails_closed():
    service = MultiAccountPortfolioManagerService()
    record = service.create(payload(upstream_risk_brain_blocked=True))
    assert record.state == MultiAccountPortfolioState.BLOCKED


def test_excludes_degraded_and_unapproved_accounts():
    service = MultiAccountPortfolioManagerService()
    accounts = payload().accounts
    accounts[0].health_score = 30
    accounts[1].prop_rules_approved = False
    record = service.create(payload(accounts=accounts))
    assert record.state == MultiAccountPortfolioState.CAPACITY_EXHAUSTED
    assert all(item.excluded for item in record.allocations)


def test_capacity_and_heat_guards():
    service = MultiAccountPortfolioManagerService()
    record = service.create(payload(max_portfolio_risk=800, requested_total_risk=500, max_portfolio_heat_pct=90))
    assert record.state in {MultiAccountPortfolioState.CAPITAL_CONSTRAINED, MultiAccountPortfolioState.CAPACITY_EXHAUSTED}


def test_human_approval_required():
    service = MultiAccountPortfolioManagerService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="human approval"):
        service.execute(record.id, "ws-a", MultiAccountAllocationExecuteRequest(actor_id="tester"))


def test_duplicate_and_workspace_isolation():
    service = MultiAccountPortfolioManagerService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="duplicate"):
        service.create(payload())
    assert service.get(record.id, "ws-b") is None
    assert service.list_records("ws-b") == []
