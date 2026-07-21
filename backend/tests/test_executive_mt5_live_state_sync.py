import pytest

from app.executive_mt5_live_state_sync.models import LiveSyncCreate, LiveSyncExecuteRequest, LiveSyncState
from app.executive_mt5_live_state_sync.service import LiveStateSyncService


class FakeProvider:
    def __init__(self, *, login=1001, positions=None, orders=None, deals=None):
        self.login = login
        self.positions = positions or []
        self.orders = orders or []
        self.deals = deals or []

    def snapshot(self, history_from_epoch):
        return {
            "account": {"login": self.login, "balance": 10000, "equity": 10025, "margin": 100, "margin_free": 9925, "margin_level": 10025, "profit": 25},
            "positions": self.positions,
            "orders": self.orders,
            "deals": self.deals,
            "order_history": [],
        }


def payload(**overrides):
    data = dict(
        workspace_id="ws-a",
        source_key="sync-1",
        actor_id="tester",
        executor_reconciliation_required=True,
        account_login=1001,
        approved_account_logins=[1001],
        account_risk_approved=True,
        prop_rules_approved=True,
    )
    data.update(overrides)
    return LiveSyncCreate(**data)


def test_requires_executor_reconciliation_evidence():
    service = LiveStateSyncService(FakeProvider())
    record = service.create(payload(executor_reconciliation_required=False))
    assert record.state == LiveSyncState.EXECUTOR_REQUIRED


def test_risk_brain_blocks_sync():
    service = LiveStateSyncService(FakeProvider())
    assert service.create(payload(risk_brain_blocked=True)).state == LiveSyncState.BLOCKED


def test_rejects_unapproved_account():
    service = LiveStateSyncService(FakeProvider())
    assert service.create(payload(approved_account_logins=[2002])).state == LiveSyncState.ACCOUNT_MISMATCH


def test_synchronizes_matching_terminal_state():
    provider = FakeProvider(positions=[{"ticket": 11, "symbol": "XAUUSD", "volume": 0.1}], deals=[{"ticket": 21, "profit": 10, "swap": 0, "commission": -1}])
    service = LiveStateSyncService(provider)
    record = service.create(payload(expected_positions=[{"broker_ticket": 11, "symbol": "XAUUSD", "volume": 0.1}], expected_deal_tickets=[21]))
    record = service.execute(record.id, "ws-a", LiveSyncExecuteRequest(actor_id="tester"))
    assert record.state == LiveSyncState.SYNCHRONIZED
    assert record.account.daily_profit == 9


def test_detects_manual_trade():
    service = LiveStateSyncService(FakeProvider(positions=[{"ticket": 99, "symbol": "EURUSD", "volume": 0.1}]))
    record = service.create(payload())
    record = service.execute(record.id, "ws-a", LiveSyncExecuteRequest(actor_id="tester"))
    assert record.state == LiveSyncState.MANUAL_TRADE_DETECTED
    assert record.manual_trade_tickets == [99]


def test_detects_partial_close():
    service = LiveStateSyncService(FakeProvider(positions=[{"ticket": 11, "symbol": "XAUUSD", "volume": 0.05}]))
    record = service.create(payload(expected_positions=[{"broker_ticket": 11, "symbol": "XAUUSD", "volume": 0.1}]))
    record = service.execute(record.id, "ws-a", LiveSyncExecuteRequest(actor_id="tester"))
    assert record.state == LiveSyncState.PARTIAL_CLOSE_DETECTED


def test_detects_missing_position_and_order():
    service = LiveStateSyncService(FakeProvider())
    position = service.create(payload(expected_positions=[{"broker_ticket": 11, "symbol": "XAUUSD", "volume": 0.1}]))
    position = service.execute(position.id, "ws-a", LiveSyncExecuteRequest(actor_id="tester"))
    assert position.state == LiveSyncState.POSITION_MISMATCH
    order = service.create(payload(source_key="sync-2", expected_orders=[{"broker_ticket": 12, "symbol": "XAUUSD", "volume": 0.1}]))
    order = service.execute(order.id, "ws-a", LiveSyncExecuteRequest(actor_id="tester"))
    assert order.state == LiveSyncState.ORDER_MISMATCH


def test_detects_missing_deal():
    service = LiveStateSyncService(FakeProvider())
    record = service.create(payload(expected_deal_tickets=[21]))
    record = service.execute(record.id, "ws-a", LiveSyncExecuteRequest(actor_id="tester"))
    assert record.state == LiveSyncState.DEAL_MISMATCH


def test_terminal_account_mismatch_fails_closed():
    service = LiveStateSyncService(FakeProvider(login=2002))
    record = service.create(payload())
    record = service.execute(record.id, "ws-a", LiveSyncExecuteRequest(actor_id="tester"))
    assert record.state == LiveSyncState.ACCOUNT_MISMATCH


def test_complete_reconciliation_requires_synchronized_state():
    service = LiveStateSyncService(FakeProvider())
    record = service.create(payload())
    with pytest.raises(ValueError):
        service.execute(record.id, "ws-a", LiveSyncExecuteRequest(actor_id="tester", action="complete-reconciliation"))
    record = service.execute(record.id, "ws-a", LiveSyncExecuteRequest(actor_id="tester"))
    record = service.execute(record.id, "ws-a", LiveSyncExecuteRequest(actor_id="tester", action="complete-reconciliation"))
    assert record.state == LiveSyncState.RECONCILIATION_COMPLETE


def test_duplicate_source_key_and_workspace_isolation():
    service = LiveStateSyncService(FakeProvider())
    record = service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.get(record.id, "ws-b") is None
    assert service.list_records("ws-b") == []


def test_audit_and_status_are_workspace_scoped():
    service = LiveStateSyncService(FakeProvider())
    record = service.create(payload())
    service.execute(record.id, "ws-a", LiveSyncExecuteRequest(actor_id="tester"))
    assert service.status("ws-a").synchronized_records == 1
    assert len(service.audit_records("ws-a")) == 2
    assert service.status("ws-b").total_records == 0
