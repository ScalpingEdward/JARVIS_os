import pytest
from pydantic import ValidationError

from app.trade_approval.models import (
    ApprovalDecision,
    KillSwitchUpdate,
    TradeApprovalCreate,
)
from app.trade_approval.service import TradeApprovalService


def payload(**overrides) -> TradeApprovalCreate:
    values = {
        "account_id": "ftmo-100k",
        "symbol": "xauusd",
        "direction": "long",
        "setup_tag": "FVG liquidity sweep",
        "requested_risk_amount": 500,
        "allocated_risk_amount": 500,
        "reward_to_risk": 2,
        "playbook_approved": True,
        "daily_drawdown_safe": True,
        "total_drawdown_safe": True,
        "spread_safe": True,
        "news_window_clear": True,
        "correlation_safe": True,
        "manual_approval": True,
    }
    values.update(overrides)
    return TradeApprovalCreate(**values)


def test_clean_trade_is_approved_but_not_executed() -> None:
    service = TradeApprovalService()
    record = service.evaluate(payload())
    assert record.decision == ApprovalDecision.APPROVED
    assert record.execution_permitted is False
    assert record.blockers == []


def test_missing_manual_approval_holds_trade() -> None:
    service = TradeApprovalService()
    record = service.evaluate(payload(manual_approval=False))
    assert record.decision == ApprovalDecision.HOLD
    assert any("not approved" in item for item in record.blockers)


def test_risk_or_drawdown_failure_blocks_trade() -> None:
    service = TradeApprovalService()
    record = service.evaluate(
        payload(allocated_risk_amount=250, daily_drawdown_safe=False)
    )
    assert record.decision == ApprovalDecision.BLOCKED
    assert any("drawdown" in item.lower() for item in record.blockers)
    assert any("allocated" in item.lower() for item in record.blockers)


def test_global_kill_switch_blocks_all_trades() -> None:
    service = TradeApprovalService()
    service.update_kill_switch(KillSwitchUpdate(active=True, reason="Emergency risk stop"))
    record = service.evaluate(payload())
    assert service.kill_switch().active is True
    assert record.decision == ApprovalDecision.BLOCKED
    assert any("kill switch" in item.lower() for item in record.blockers)


def test_records_can_be_listed_and_retrieved() -> None:
    service = TradeApprovalService()
    record = service.evaluate(payload())
    assert service.get(record.id) == record
    assert service.list_all() == [record]


def test_unsafe_payloads_and_unapproved_kill_switch_are_rejected() -> None:
    with pytest.raises(ValidationError):
        payload(automatic_execution=True)
    with pytest.raises(ValidationError):
        KillSwitchUpdate(active=True, reason="")
    with pytest.raises(ValidationError):
        KillSwitchUpdate(active=True, reason="Emergency", human_approved=False)
