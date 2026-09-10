import pytest

from app.modules.dynamic_risk_engine.models import (
    AccountRiskSnapshot,
    DynamicRiskCreate,
    RiskAction,
    RiskCommand,
    RiskPolicy,
    RiskState,
)
from app.modules.dynamic_risk_engine.service import DynamicRiskError, DynamicRiskService


@pytest.fixture(autouse=True)
def _reset_shared_state():
    """Storage is now real and shared (see DynamicRiskService's own
    docstring) rather than fresh-per-instance in-memory -- tests in this
    file reuse fixed workspace_id/source_key values across each other on
    purpose (to test duplicate-detection itself), so each test needs a
    clean slate rather than relying on a brand new DynamicRiskService()
    implying empty state the way it used to."""
    DynamicRiskService().reset()
    yield


def payload(**overrides) -> DynamicRiskCreate:
    data = {
        "workspace_id": "desk-a",
        "source_key": "risk-001",
        "position_management_record_id": "position-1",
        "v21_16_approved": True,
        "v21_16_evidence": {"state": "approved", "setup_grade": "A+"},
        "symbol": "XAUUSD",
        "direction": "long",
        "setup_grade": "A+",
        "setup_confidence_score": 90,
        "entry_price": 2400.0,
        "stop_price": 2390.0,
        "value_per_price_unit": 1.0,
        "account": AccountRiskSnapshot(
            balance=100000,
            equity=100000,
            daily_start_equity=100000,
            initial_account_size=100000,
            open_risk_amount=0,
            consecutive_losses=0,
            volatility_score=40,
            correlation_exposure_score=20,
        ),
        "policy": RiskPolicy(
            base_risk_percent=0.5,
            minimum_risk_percent=0.1,
            maximum_risk_percent=1.0,
            maximum_daily_loss_percent=4,
            maximum_total_drawdown_percent=10,
            maximum_aggregate_open_risk_percent=2,
        ),
    }
    data.update(overrides)
    return DynamicRiskCreate(**data)


def test_a_plus_setup_receives_governed_risk() -> None:
    service = DynamicRiskService()
    record = service.create(payload())
    assert record.state == RiskState.RISK_APPROVED
    assert 0.5 < record.assessment.recommended_risk_percent <= 1.0
    assert record.assessment.recommended_risk_amount > 0
    assert record.assessment.recommended_position_units > 0


def test_losing_streak_and_volatility_reduce_risk() -> None:
    service = DynamicRiskService()
    account = payload().account.model_copy(update={"consecutive_losses": 2, "volatility_score": 90})
    record = service.create(payload(account=account))
    assert record.state == RiskState.HUMAN_REVIEW_REQUIRED
    assert record.assessment.recommended_risk_percent < 0.5
    assert record.assessment.warnings


def test_daily_loss_and_drawdown_limits_fail_closed() -> None:
    service = DynamicRiskService()
    daily = payload().account.model_copy(update={"equity": 95000, "daily_start_equity": 100000})
    drawdown = payload().account.model_copy(update={"equity": 89000, "daily_start_equity": 89000})
    daily_record = service.create(payload(source_key="daily", account=daily))
    drawdown_record = service.create(payload(source_key="drawdown", account=drawdown))
    assert daily_record.state == RiskState.BLOCKED
    assert drawdown_record.state == RiskState.BLOCKED
    assert daily_record.assessment.recommended_risk_amount == 0
    assert drawdown_record.assessment.recommended_position_units == 0


def test_missing_evidence_and_risk_brain_block() -> None:
    service = DynamicRiskService()
    missing = service.create(payload(source_key="missing", v21_16_evidence={}))
    blocked = service.create(payload(source_key="blocked", risk_brain_hard_block=True))
    assert missing.state == RiskState.EVIDENCE_REQUIRED
    assert blocked.state == RiskState.BLOCKED


def test_approval_issue_and_replay_protection() -> None:
    service = DynamicRiskService()
    first = service.create(payload(source_key="first"))
    service.execute(
        "desk-a",
        first.id,
        RiskAction(command=RiskCommand.APPROVE, actor="brano", approval_token="approval-1"),
    )
    issued = service.execute(
        "desk-a",
        first.id,
        RiskAction(command=RiskCommand.ISSUE, actor="brano", downstream_receipt="exposure-1"),
    )
    assert issued.state == RiskState.ISSUED_TO_EXPOSURE_MANAGER

    second = service.create(payload(source_key="second"))
    with pytest.raises(DynamicRiskError, match="approval token replay"):
        service.execute(
            "desk-a",
            second.id,
            RiskAction(command=RiskCommand.APPROVE, actor="brano", approval_token="approval-1"),
        )


def test_open_risk_capacity_is_enforced() -> None:
    service = DynamicRiskService()
    account = payload().account.model_copy(update={"open_risk_amount": 1950})
    record = service.create(payload(account=account))
    assert record.state == RiskState.BLOCKED
    assert record.assessment.recommended_risk_percent == 0


def test_duplicate_source_and_workspace_isolation() -> None:
    service = DynamicRiskService()
    record = service.create(payload())
    with pytest.raises(DynamicRiskError, match="duplicate source_key"):
        service.create(payload())
    with pytest.raises(DynamicRiskError, match="record not found"):
        service.get("desk-b", record.id)


def test_invalid_long_geometry_is_rejected() -> None:
    with pytest.raises(ValueError, match="long stop"):
        payload(stop_price=2410.0)


def test_symbol_case_is_preserved_exactly() -> None:
    """Same bug class as position_management_brain (#963): broker symbol
    suffixes are case-sensitive, and downstream live-quote/contract-spec
    lookups do an exact string match against mt5_bridge. Found live on the
    same real-account pipeline run that caught the position_management_brain
    version."""
    service = DynamicRiskService()
    record = service.create(payload(symbol="XAUUSD.s"))
    assert record.symbol == "XAUUSD.s"


# -- the fix: real persistence, including replay protection across restart --


def test_records_and_audit_survive_a_fresh_service_instance_simulating_a_restart() -> None:
    first_instance = DynamicRiskService()
    record = first_instance.create(payload())
    first_instance.execute(
        "desk-a", record.id, RiskAction(command=RiskCommand.APPROVE, actor="brano", approval_token="tok-1"),
    )

    second_instance = DynamicRiskService()  # nothing shared but the real database
    restored = second_instance.get("desk-a", record.id)
    assert restored.state == RiskState.APPROVED
    assert restored.approval_token == "tok-1"
    audit = second_instance.audit("desk-a")
    assert any(event.action == "approve" for event in audit)


def test_an_approval_token_cannot_be_replayed_after_a_simulated_restart() -> None:
    """The narrower, real security property this fix closes: previously,
    a restart right after a token was spent would have forgotten it was
    ever used, since the replay-protection set was in-memory only -- the
    same token could then be replayed against a different risk record."""
    first_instance = DynamicRiskService()
    first_record = first_instance.create(payload(source_key="first"))
    first_instance.execute(
        "desk-a", first_record.id,
        RiskAction(command=RiskCommand.APPROVE, actor="brano", approval_token="tok-shared"),
    )

    # A brand new instance -- simulates the process having restarted.
    second_instance = DynamicRiskService()
    second_record = second_instance.create(payload(source_key="second"))
    with pytest.raises(DynamicRiskError, match="approval token replay"):
        second_instance.execute(
            "desk-a", second_record.id,
            RiskAction(command=RiskCommand.APPROVE, actor="brano", approval_token="tok-shared"),
        )
