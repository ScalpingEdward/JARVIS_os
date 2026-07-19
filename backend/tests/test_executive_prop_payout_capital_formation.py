import pytest

from app.executive_prop_payout_capital_formation.models import (
    CapitalPolicy,
    FormationAssessmentCreate,
    FormationState,
    PayoutStatus,
    PropPayout,
    UseCategory,
)
from app.executive_prop_payout_capital_formation.service import ExecutivePropPayoutCapitalFormationService


def payload(workspace: str = "ws-1", approved: bool = True, status: PayoutStatus = PayoutStatus.RECEIVED):
    return FormationAssessmentCreate(
        workspace_id=workspace,
        source_key=f"source-{workspace}-{approved}-{status.value}",
        actor_id="master-brano",
        payouts=[PropPayout(
            prop_firm="FTMO",
            account_label="100k-01",
            payout_amount=10000,
            status=status,
            account_nominal_size=100000,
        )],
        policy=CapitalPolicy(),
        human_approval=approved,
    )


def test_received_payout_builds_live_capital_not_prop_nominal_capital():
    service = ExecutivePropPayoutCapitalFormationService()
    result = service.create(payload())
    assert result.state == FormationState.APPROVED
    assert result.received_cash == 10000
    assert result.prop_nominal_capital == 100000
    assert result.live_capital_contribution == 3000
    assert result.protected_reserves == 3500


def test_expected_payout_is_not_allocated():
    service = ExecutivePropPayoutCapitalFormationService()
    result = service.create(payload(status=PayoutStatus.CONFIRMED))
    assert result.state == FormationState.HOLD
    assert result.received_cash == 0
    assert result.expected_cash == 10000
    assert all(line.amount == 0 for line in result.allocations)


def test_human_approval_required_for_deployable_plan():
    service = ExecutivePropPayoutCapitalFormationService()
    result = service.create(payload(approved=False))
    assert result.state == FormationState.PLAN
    assert all(not line.deployable for line in result.allocations)


def test_prop_growth_is_budget_for_new_challenges_only():
    service = ExecutivePropPayoutCapitalFormationService()
    result = service.create(payload())
    line = next(line for line in result.allocations if line.category == UseCategory.PROP_GROWTH)
    assert line.amount == 1000
    assert result.prop_growth_budget == 1000


def test_duplicate_source_key_is_rejected():
    service = ExecutivePropPayoutCapitalFormationService()
    request = payload()
    service.create(request)
    with pytest.raises(ValueError):
        service.create(request)


def test_workspace_isolation():
    service = ExecutivePropPayoutCapitalFormationService()
    created = service.create(payload("alpha"))
    assert service.get(created.assessment_id, "beta") is None
