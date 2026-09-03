import pytest

from app.modules.position_management_brain.models import ExitRule, PositionAction, PositionCommand, PositionCreate, PositionState
from app.modules.position_management_brain.service import PositionManagementError, PositionManagementService


def payload(**overrides) -> PositionCreate:
    data = {
        "workspace_id": "desk-a",
        "source_key": "xau-position-1",
        "trade_setup_record_id": "setup-1",
        "v21_15_approved": True,
        "v21_15_evidence": {"grade": "A+", "state": "approved"},
        "symbol": "XAUUSD",
        "direction": "long",
        "entry_price": 2400.0,
        "initial_stop_price": 2390.0,
        "position_size": 1.0,
        "risk_amount": 1000,
        "exit_rules": [
            ExitRule(key="tp1", kind="take-profit", trigger_price=2420, close_percent=50, evidence_ref="setup:tp1"),
            ExitRule(key="be", kind="break-even", stop_price=2400, evidence_ref="policy:be"),
            ExitRule(key="structure-exit", kind="structure-exit", evidence_ref="market:choch"),
        ],
    }
    data.update(overrides)
    return PositionCreate(**data)


def open_position(service: PositionManagementService, source_key: str = "xau-position-1"):
    record = service.create(payload(source_key=source_key))
    service.execute("desk-a", record.id, PositionAction(command=PositionCommand.APPROVE, actor="brano", approval_token=f"approve-{source_key}"))
    return service.execute("desk-a", record.id, PositionAction(command=PositionCommand.MARK_OPEN, actor="broker-adapter", downstream_receipt=f"open-{source_key}"))


def test_approve_open_protect_and_scale_out() -> None:
    service = PositionManagementService()
    record = open_position(service)
    assert record.state == PositionState.OPEN
    record = service.execute("desk-a", record.id, PositionAction(command=PositionCommand.APPLY_RULE, actor="phoenix", rule_key="be"))
    assert record.state == PositionState.PROTECTED
    assert record.current_stop_price == 2400
    record = service.execute("desk-a", record.id, PositionAction(command=PositionCommand.APPLY_RULE, actor="phoenix", rule_key="tp1"))
    assert record.state == PositionState.SCALING_OUT
    assert record.remaining_percent == 50


def test_structure_rule_recommends_exit() -> None:
    service = PositionManagementService()
    record = open_position(service)
    record = service.execute("desk-a", record.id, PositionAction(command=PositionCommand.APPLY_RULE, actor="phoenix", rule_key="structure-exit"))
    assert record.state == PositionState.EXIT_RECOMMENDED


def test_news_risk_and_upstream_gates() -> None:
    service = PositionManagementService()
    review = service.create(payload(active_news_risk=True))
    missing = service.create(payload(source_key="missing", v21_15_evidence={}))
    blocked = service.create(payload(source_key="blocked", risk_brain_hard_block=True))
    assert review.state == PositionState.HUMAN_REVIEW_REQUIRED
    assert missing.state == PositionState.EVIDENCE_REQUIRED
    assert blocked.state == PositionState.BLOCKED


def test_stop_cannot_be_loosened() -> None:
    service = PositionManagementService()
    request = payload(exit_rules=[ExitRule(key="bad", kind="swing-trail", stop_price=2380, evidence_ref="swing")])
    record = service.create(request)
    service.execute("desk-a", record.id, PositionAction(command=PositionCommand.APPROVE, actor="brano"))
    service.execute("desk-a", record.id, PositionAction(command=PositionCommand.MARK_OPEN, actor="adapter", downstream_receipt="open-bad"))
    with pytest.raises(PositionManagementError, match="cannot be loosened"):
        service.execute("desk-a", record.id, PositionAction(command=PositionCommand.APPLY_RULE, actor="phoenix", rule_key="bad"))


def test_replay_duplicate_and_workspace_isolation() -> None:
    service = PositionManagementService()
    first = service.create(payload())
    service.execute("desk-a", first.id, PositionAction(command=PositionCommand.APPROVE, actor="brano", approval_token="same-token"))
    second = service.create(payload(source_key="second"))
    with pytest.raises(PositionManagementError, match="replay"):
        service.execute("desk-a", second.id, PositionAction(command=PositionCommand.APPROVE, actor="brano", approval_token="same-token"))
    with pytest.raises(PositionManagementError, match="duplicate"):
        service.create(payload())
    with pytest.raises(PositionManagementError, match="not found"):
        service.get("desk-b", first.id)


def test_close_records_realized_r() -> None:
    service = PositionManagementService()
    record = open_position(service)
    record = service.execute("desk-a", record.id, PositionAction(command=PositionCommand.CLOSE, actor="brano", realized_r_multiple=2.4))
    assert record.state == PositionState.CLOSED
    assert record.remaining_percent == 0
    assert record.realized_r_multiple == 2.4


def test_symbol_case_is_preserved_exactly() -> None:
    """Broker symbol suffixes are case-sensitive (e.g. 'XAUUSD.s' vs
    'XAUUSD.S' can be different tradeable symbols, or the live-quote lookup
    against mt5_bridge is an exact string match either way). The service
    must never silently uppercase the symbol it was given -- found live
    while testing against a real broker where this exact mismatch broke
    the quote lookup."""
    service = PositionManagementService()
    record = service.create(payload(source_key="lowercase-symbol", symbol="XAUUSD.s"))
    assert record.symbol == "XAUUSD.s"
