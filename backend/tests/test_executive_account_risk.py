from uuid import uuid4

import pytest

from app.executive_account_risk.models import AccountRiskAssessmentCreate, AccountRiskObservation, AccountRiskState, RiskReductionRequest
from app.executive_account_risk.service import executive_account_risk_service


@pytest.fixture(autouse=True)
def reset_service() -> None:
    executive_account_risk_service.reset()


def payload(**observation_overrides):
    observation_values = {
        "balance": 100_000,
        "equity": 99_000,
        "start_of_day_balance": 100_000,
        "initial_account_balance": 100_000,
        "used_margin": 10_000,
        "free_margin": 89_000,
        "gross_exposure": 30_000,
        "net_exposure": 20_000,
        "largest_symbol_exposure_pct": 20,
        "largest_strategy_exposure_pct": 30,
        "correlated_exposure_pct": 40,
        "open_risk_pct": 1.5,
        "pending_order_risk_pct": 0.5,
    }
    observation_values.update(observation_overrides)
    observation = AccountRiskObservation(**observation_values)
    return AccountRiskAssessmentCreate(
        workspace_id="master-brano",
        source_key=str(uuid4()),
        actor_id="master-brano",
        account_reference="prop-100k",
        broker_reference="broker-a",
        observation=observation,
    )


def test_account_risk_clear() -> None:
    record = executive_account_risk_service.assess(payload())
    assert record.state == AccountRiskState.account_risk_clear
    assert record.daily_loss_pct == 1
    assert record.reduction_required is False


def test_position_dependency_required() -> None:
    record = executive_account_risk_service.assess(payload(position_lifecycle_state="protection-required"))
    assert record.state == AccountRiskState.position_data_required


def test_broker_reconciliation_required() -> None:
    record = executive_account_risk_service.assess(payload(broker_equity_reconciled=False))
    assert record.state == AccountRiskState.broker_reconciliation_required


def test_daily_loss_breach() -> None:
    record = executive_account_risk_service.assess(payload(equity=95_000))
    assert record.state == AccountRiskState.daily_loss_breached


def test_maximum_drawdown_breach() -> None:
    record = executive_account_risk_service.assess(payload(equity=89_000, start_of_day_balance=90_000))
    assert record.state == AccountRiskState.drawdown_breached


def test_margin_stress() -> None:
    record = executive_account_risk_service.assess(payload(used_margin=80_000))
    assert record.state == AccountRiskState.margin_stressed


def test_concentration_breach() -> None:
    record = executive_account_risk_service.assess(payload(largest_symbol_exposure_pct=50))
    assert record.state == AccountRiskState.exposure_concentrated


def test_correlation_breach() -> None:
    record = executive_account_risk_service.assess(payload(correlated_exposure_pct=70))
    assert record.state == AccountRiskState.correlation_breached


def test_risk_brain_block() -> None:
    request = payload()
    request.risk_brain_clear = False
    record = executive_account_risk_service.assess(request)
    assert record.state == AccountRiskState.blocked


def test_duplicate_source_key_rejected() -> None:
    request = payload()
    executive_account_risk_service.assess(request)
    with pytest.raises(ValueError):
        executive_account_risk_service.assess(request)


def test_workspace_isolation() -> None:
    record = executive_account_risk_service.assess(payload())
    assert executive_account_risk_service.get(record.id, "other-workspace") is None


def test_human_approved_risk_reduction() -> None:
    record = executive_account_risk_service.assess(payload(open_risk_pct=4))
    reduced = executive_account_risk_service.reduce(
        RiskReductionRequest(
            workspace_id=record.workspace_id,
            assessment_id=record.assessment_id,
            actor_id="master-brano",
            human_approval_verified=True,
            reduction_acknowledged=True,
            updated_equity=99_000,
            updated_used_margin=5_000,
            updated_open_risk_pct=1,
        )
    )
    assert reduced.state == AccountRiskState.account_risk_clear
    assert reduced.total_open_risk_pct == 1
