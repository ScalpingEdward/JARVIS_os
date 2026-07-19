import pytest

from app.executive_treasury_wealth_governance.models import TreasuryAssessmentCreate, TreasuryPolicy, TreasuryState
from app.executive_treasury_wealth_governance.service import ExecutiveTreasuryWealthGovernanceService


def payload(**overrides):
    data = dict(
        workspace_id="wealth-a",
        source_key="treasury-1",
        actor_id="master-brano",
        owned_cash=10000,
        received_prop_payout_cash=5000,
        existing_tax_reserve=3000,
        existing_emergency_reserve=6000,
        existing_live_trading_capital=2000,
        existing_long_term_investments=1000,
        requested_withdrawal=500,
        human_approved=True,
        prop_nominal_capital=200000,
        policy=TreasuryPolicy(
            minimum_tax_reserve=3000,
            minimum_emergency_reserve=6000,
            monthly_living_costs=1000,
            minimum_runway_months=6,
        ),
    )
    data.update(overrides)
    return TreasuryAssessmentCreate(**data)


def test_growth_ready_uses_only_owned_capital():
    service = ExecutiveTreasuryWealthGovernanceService()
    result = service.create(payload())
    assert result.state == TreasuryState.growth_ready
    assert result.owned_capital == 15000
    assert result.excluded_prop_nominal_capital == 200000
    assert result.growth_capital > 0
    assert result.autonomous_actions_enabled is False


def test_reserve_gap_forces_preservation():
    service = ExecutiveTreasuryWealthGovernanceService()
    result = service.create(payload(source_key="treasury-2", existing_tax_reserve=0, existing_emergency_reserve=0))
    assert result.state == TreasuryState.preserve
    assert all(not line.deployable or line.bucket.value in {"tax-reserve", "emergency-reserve"} for line in result.allocation_lines)


def test_human_approval_gates_growth_lines():
    service = ExecutiveTreasuryWealthGovernanceService()
    result = service.create(payload(source_key="treasury-3", human_approved=False))
    assert result.state == TreasuryState.balanced
    assert result.approved_withdrawal == 0
    assert not any(line.deployable for line in result.allocation_lines if line.bucket.value in {"live-trading", "long-term-investing", "opportunity-cash"})


def test_large_withdrawal_requires_review():
    service = ExecutiveTreasuryWealthGovernanceService()
    result = service.create(payload(source_key="treasury-4", requested_withdrawal=3000))
    assert result.state == TreasuryState.withdrawal_review
    assert result.approved_withdrawal <= result.owned_capital * 0.10


def test_duplicate_and_workspace_isolation():
    service = ExecutiveTreasuryWealthGovernanceService()
    record = service.create(payload(source_key="treasury-5"))
    with pytest.raises(ValueError):
        service.create(payload(source_key="treasury-5"))
    assert service.get(record.id, "wealth-b") is None
    assert service.list("wealth-b") == []
