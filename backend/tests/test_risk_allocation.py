import pytest
from pydantic import ValidationError

from app.risk_allocation.models import AccountInput, AccountState, AllocationCreate
from app.risk_allocation.service import RiskAllocationService


def account(**overrides) -> AccountInput:
    values = {
        "account_id": "ftmo-100k",
        "provider": "FTMO",
        "balance": 100000,
        "daily_drawdown_remaining": 5000,
        "total_drawdown_remaining": 10000,
        "requested_risk_pct": 1,
        "correlation_group": "xauusd",
    }
    values.update(overrides)
    return AccountInput(**values)


def payload(**overrides) -> AllocationCreate:
    values = {
        "name": "MASTER Brano multi-account plan",
        "portfolio_risk_budget_pct": 2,
        "max_account_risk_pct": 1,
        "max_correlation_group_risk_pct": 1.5,
        "safety_buffer_pct": 20,
        "accounts": [
            account(),
            account(
                account_id="e8-100k",
                provider="E8",
                correlation_group="nas100",
            ),
        ],
    }
    values.update(overrides)
    return AllocationCreate(**values)


def test_allocates_risk_across_accounts() -> None:
    service = RiskAllocationService()
    plan = service.create(payload())
    assert plan.total_balance == 200000
    assert plan.portfolio_risk_budget_amount == 4000
    assert plan.allocated_risk_amount == 2000
    assert all(item.state == AccountState.ACTIVE for item in plan.allocations)


def test_correlation_limit_reduces_second_account() -> None:
    service = RiskAllocationService()
    plan = service.create(
        payload(
            accounts=[
                account(account_id="a", requested_risk_pct=2),
                account(account_id="b", requested_risk_pct=2),
            ],
            max_account_risk_pct=2,
            max_correlation_group_risk_pct=1.5,
        )
    )
    assert plan.correlation_group_allocations["xauusd"] == 3000
    assert plan.allocations[0].allocated_risk_amount == 2000
    assert plan.allocations[1].allocated_risk_amount == 1000
    assert plan.allocations[1].state == AccountState.CAUTION


def test_drawdown_capacity_can_block_account() -> None:
    service = RiskAllocationService()
    plan = service.create(
        payload(accounts=[account(daily_drawdown_remaining=0, total_drawdown_remaining=0)])
    )
    assert plan.allocations[0].state == AccountState.BLOCKED
    assert plan.allocations[0].allocated_risk_amount == 0
    assert plan.blockers


def test_plans_can_be_listed_and_retrieved() -> None:
    service = RiskAllocationService()
    plan = service.create(payload())
    assert service.get(plan.id) == plan
    assert service.list_all() == [plan]


def test_unsafe_or_duplicate_payloads_are_rejected() -> None:
    with pytest.raises(ValidationError):
        payload(automatic_execution=True)
    with pytest.raises(ValidationError):
        payload(human_approved=False)
    with pytest.raises(ValidationError):
        payload(accounts=[account(), account()])