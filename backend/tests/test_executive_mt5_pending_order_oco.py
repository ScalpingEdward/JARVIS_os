from datetime import datetime, timedelta, timezone

import pytest

from app.executive_mt5_pending_order_oco.models import PendingOrderAssessmentCreate, PendingOrderExecuteRequest, PendingOrderState
from app.executive_mt5_pending_order_oco.service import PendingOrderOCOService


def payload(**overrides):
    data = dict(
        workspace_id="ws-a",
        source_key="signal-1",
        actor_id="tester",
        profit_lock_ready=True,
        symbol="XAUUSD",
        order_type="buy_stop",
        volume=0.10,
        entry_price=2401.0,
        current_bid=2400.0,
        current_ask=2400.2,
        point=0.01,
        stop_level_points=20,
        freeze_level_points=10,
        expiration_at=datetime.now(timezone.utc) + timedelta(hours=1),
        account_risk_approved=True,
        prop_rules_approved=True,
    )
    data.update(overrides)
    return PendingOrderAssessmentCreate(**data)


def test_requires_profit_lock_dependency():
    service = PendingOrderOCOService()
    record = service.create(payload(profit_lock_ready=False))
    assert record.state == PendingOrderState.PROFIT_LOCK_REQUIRED


def test_rejects_invalid_order_type():
    service = PendingOrderOCOService()
    record = service.create(payload(order_type="market"))
    assert record.state == PendingOrderState.REQUEST_INVALID


def test_rejects_entry_inside_broker_distance():
    service = PendingOrderOCOService()
    record = service.create(payload(entry_price=2400.25))
    assert record.state == PendingOrderState.PRICE_INVALID


def test_rejects_expired_order():
    service = PendingOrderOCOService()
    record = service.create(payload(expiration_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    assert record.state == PendingOrderState.EXPIRATION_INVALID


def test_oco_requires_peer_definition():
    service = PendingOrderOCOService()
    record = service.create(payload(oco_group_id="oco-1", peer_order_defined=False))
    assert record.state == PendingOrderState.OCO_INVALID


def test_risk_brain_is_hard_block():
    service = PendingOrderOCOService()
    record = service.create(payload(risk_brain_blocked=True, human_approved=True))
    assert record.state == PendingOrderState.BLOCKED


def test_requires_human_approval():
    service = PendingOrderOCOService()
    record = service.create(payload())
    assert record.state == PendingOrderState.APPROVAL_REQUIRED


def test_oco_pair_becomes_armed_after_acknowledgement():
    service = PendingOrderOCOService()
    record = service.create(payload(oco_group_id="oco-1", peer_order_defined=True))
    executed = service.execute(
        record.id,
        "ws-a",
        PendingOrderExecuteRequest(
            actor_id="operator",
            broker_order_id="12345",
            broker_retcode=10009,
        ),
    )
    assert executed.state == PendingOrderState.OCO_ARMED


def test_peer_cancel_required_until_acknowledged():
    service = PendingOrderOCOService()
    record = service.create(payload(oco_group_id="oco-1", peer_order_defined=True))
    executed = service.execute(
        record.id,
        "ws-a",
        PendingOrderExecuteRequest(
            actor_id="operator",
            broker_order_id="12345",
            broker_retcode=10009,
            peer_cancel_acknowledged=False,
        ),
    )
    executed.payload.peer_cancel_required = True
    state, _ = service._evaluate(executed.payload)
    assert state == PendingOrderState.CANCEL_PENDING


def test_non_oco_order_reaches_pending_ready_after_reconciliation():
    service = PendingOrderOCOService()
    record = service.create(payload())
    executed = service.execute(
        record.id,
        "ws-a",
        PendingOrderExecuteRequest(
            actor_id="operator",
            broker_order_id="12345",
            broker_retcode=10009,
            pending_orders_reconciled=True,
            account_snapshot_reconciled=True,
        ),
    )
    assert executed.state == PendingOrderState.PENDING_READY


def test_terminal_error_fails_execution():
    service = PendingOrderOCOService()
    record = service.create(payload())
    executed = service.execute(record.id, "ws-a", PendingOrderExecuteRequest(actor_id="operator", terminal_error="MT5 unavailable"))
    assert executed.state == PendingOrderState.FAILED


def test_duplicate_source_key_is_rejected():
    service = PendingOrderOCOService()
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())


def test_workspace_isolation():
    service = PendingOrderOCOService()
    record = service.create(payload())
    assert service.get(record.id, "ws-b") is None
    assert service.list_records("ws-b") == []
