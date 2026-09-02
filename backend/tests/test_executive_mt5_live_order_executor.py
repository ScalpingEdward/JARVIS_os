from types import SimpleNamespace

from app.executive_mt5_live_order_executor.models import LiveOrderCreate, LiveOrderExecuteRequest, LiveOrderState
from app.executive_mt5_live_order_executor.service import LiveOrderExecutorService


class FakeExecutor:
    def __init__(self, check_retcode=0, send_retcode=10009, volume=0.1):
        self.check_retcode = check_retcode
        self.send_retcode = send_retcode
        self.volume = volume

    def symbol_info(self, symbol):
        return SimpleNamespace(name=symbol)

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(bid=2000, ask=2000.2)

    def order_check(self, request):
        return SimpleNamespace(retcode=self.check_retcode, comment="check")

    def order_send(self, request):
        return SimpleNamespace(retcode=self.send_retcode, order=123, deal=456, comment="done", volume=self.volume, price=2000.2)


def payload(**updates):
    base = dict(
        workspace_id="ws-a",
        source_key="source-1",
        actor_id="tester",
        native_adapter_ready=True,
        account_login=123456,
        approved_account_logins=[123456],
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume=0.1,
        quote_bid=2000.0,
        quote_ask=2000.2,
        quote_age_seconds=1,
        symbol_point=0.01,
        min_volume=0.01,
        max_volume=10,
        volume_step=0.01,
        expected_risk_amount=50,
        max_risk_amount=100,
        account_risk_approved=True,
        prop_rules_approved=True,
        human_approved=True,
    )
    base.update(updates)
    return LiveOrderCreate(**base)


def test_requires_native_adapter():
    service = LiveOrderExecutorService(FakeExecutor())
    assert service.create(payload(native_adapter_ready=False)).state == LiveOrderState.ADAPTER_REQUIRED


def test_rejects_wrong_account():
    service = LiveOrderExecutorService(FakeExecutor())
    assert service.create(payload(account_login=999)).state == LiveOrderState.BLOCKED


def test_rejects_stale_quote():
    service = LiveOrderExecutorService(FakeExecutor())
    assert service.create(payload(quote_age_seconds=30)).state == LiveOrderState.QUOTE_STALE


def test_rejects_invalid_volume_step():
    service = LiveOrderExecutorService(FakeExecutor())
    assert service.create(payload(volume=0.015)).state == LiveOrderState.VOLUME_REJECTED


def test_rejects_invalid_stop_loss():
    service = LiveOrderExecutorService(FakeExecutor())
    assert service.create(payload(stop_loss=2001)).state == LiveOrderState.STOPS_REJECTED


def test_rejects_excess_risk():
    service = LiveOrderExecutorService(FakeExecutor())
    assert service.create(payload(expected_risk_amount=150)).state == LiveOrderState.RISK_REJECTED


def test_requires_human_approval():
    service = LiveOrderExecutorService(FakeExecutor())
    assert service.create(payload(human_approved=False)).state == LiveOrderState.APPROVAL_REQUIRED


def test_risk_brain_hard_block():
    service = LiveOrderExecutorService(FakeExecutor())
    assert service.create(payload(risk_brain_blocked=True)).state == LiveOrderState.BLOCKED


def test_successful_submission_requires_reconciliation():
    service = LiveOrderExecutorService(FakeExecutor())
    record = service.create(payload())
    updated = service.execute(record.id, "ws-a", LiveOrderExecuteRequest(actor_id="approver"))
    assert updated.state == LiveOrderState.RECONCILIATION_REQUIRED
    assert updated.broker_order_id == 123


def test_partial_fill():
    service = LiveOrderExecutorService(FakeExecutor(volume=0.05))
    record = service.create(payload())
    updated = service.execute(record.id, "ws-a", LiveOrderExecuteRequest(actor_id="approver"))
    assert updated.state == LiveOrderState.PARTIAL_FILL


def test_broker_check_rejection():
    service = LiveOrderExecutorService(FakeExecutor(check_retcode=10013))
    record = service.create(payload())
    updated = service.execute(record.id, "ws-a", LiveOrderExecuteRequest(actor_id="approver"))
    assert updated.state == LiveOrderState.BROKER_REJECTED


def test_broker_send_rejection():
    service = LiveOrderExecutorService(FakeExecutor(send_retcode=10013))
    record = service.create(payload())
    updated = service.execute(record.id, "ws-a", LiveOrderExecuteRequest(actor_id="approver"))
    assert updated.state == LiveOrderState.BROKER_REJECTED


def test_cancel_before_execution():
    service = LiveOrderExecutorService(FakeExecutor())
    record = service.create(payload(human_approved=False))
    updated = service.execute(record.id, "ws-a", LiveOrderExecuteRequest(actor_id="operator", action="cancel"))
    assert updated.state == LiveOrderState.CANCELLED


def test_duplicate_source_key_rejected():
    service = LiveOrderExecutorService(FakeExecutor())
    service.create(payload())
    try:
        service.create(payload())
        assert False, "duplicate should fail"
    except ValueError:
        assert True


def test_workspace_isolation():
    service = LiveOrderExecutorService(FakeExecutor())
    record = service.create(payload())
    assert service.get(record.id, "ws-b") is None
    assert service.list_records("ws-b") == []


# -- remote execution agent: AURON has no local native executor -----------


def test_execute_without_a_native_executor_awaits_remote_execution_instead_of_failing():
    """No executor injected, and no real MetaTrader5 package importable in
    this test environment either -- exactly the situation AURON is in when
    running in its own Docker container. Must stay PREFLIGHT_READY, not FAILED."""
    service = LiveOrderExecutorService()  # no executor injected
    record = service.create(payload())
    updated = service.execute(record.id, "ws-a", LiveOrderExecuteRequest(actor_id="approver"))
    assert updated.state == LiveOrderState.PREFLIGHT_READY
    assert "remote execution agent" in updated.detail.lower()


def test_pending_execution_lists_only_preflight_ready_records():
    service = LiveOrderExecutorService()
    ready = service.create(payload())
    service.execute(ready.id, "ws-a", LiveOrderExecuteRequest(actor_id="approver"))
    not_ready = service.create(payload(source_key="source-2", human_approved=False))

    pending = service.pending_execution("ws-a")
    assert [r.id for r in pending] == [ready.id]
    assert not_ready.id not in [r.id for r in pending]


def test_report_execution_applies_the_same_classification_as_the_native_path():
    from app.executive_mt5_live_order_executor.models import RemoteExecutionReport

    service = LiveOrderExecutorService()
    record = service.create(payload())
    service.execute(record.id, "ws-a", LiveOrderExecuteRequest(actor_id="approver"))

    reported = service.report_execution(
        record.id,
        "ws-a",
        RemoteExecutionReport(
            actor_id="windows-agent", broker_retcode=10009, broker_order_id=555, broker_deal_id=777,
            broker_comment="done", filled_volume=0.1, average_price=2000.2,
        ),
    )
    assert reported.state == LiveOrderState.RECONCILIATION_REQUIRED
    assert reported.broker_order_id == 555
    assert reported.broker_deal_id == 777


def test_report_execution_classifies_a_broker_rejection():
    from app.executive_mt5_live_order_executor.models import RemoteExecutionReport

    service = LiveOrderExecutorService()
    record = service.create(payload())
    service.execute(record.id, "ws-a", LiveOrderExecuteRequest(actor_id="approver"))

    reported = service.report_execution(
        record.id, "ws-a", RemoteExecutionReport(broker_retcode=10013, broker_comment="invalid request")
    )
    assert reported.state == LiveOrderState.BROKER_REJECTED


def test_report_execution_refuses_a_record_not_awaiting_execution():
    from app.executive_mt5_live_order_executor.models import RemoteExecutionReport

    service = LiveOrderExecutorService()
    record = service.create(payload(human_approved=False))  # still APPROVAL_REQUIRED

    try:
        service.report_execution(record.id, "ws-a", RemoteExecutionReport(broker_retcode=10009))
        assert False, "should have refused a non-preflight-ready record"
    except ValueError as exc:
        assert "not awaiting execution" in str(exc)


def test_report_execution_unknown_record_fails_closed():
    from uuid import uuid4

    from app.executive_mt5_live_order_executor.models import RemoteExecutionReport

    service = LiveOrderExecutorService()
    try:
        service.report_execution(uuid4(), "ws-a", RemoteExecutionReport(broker_retcode=10009))
        assert False, "should have raised"
    except KeyError:
        assert True
