from datetime import datetime, timezone

from app.executive_mt5_native_adapter_runtime.models import (
    AdapterRuntimeEvidence,
    NativeAdapterAssessmentCreate,
    NativeAdapterExecuteRequest,
    NativeAdapterState,
)
from app.executive_mt5_native_adapter_runtime.service import NativeAdapterRuntimeService


class FakeAdapter:
    def __init__(self, evidence: AdapterRuntimeEvidence) -> None:
        self.evidence = evidence

    def connect(self, requested_login: int, required_symbols: list[str]) -> AdapterRuntimeEvidence:
        return self.evidence

    def heartbeat(self, required_symbols: list[str]) -> AdapterRuntimeEvidence:
        return self.evidence

    def disconnect(self) -> AdapterRuntimeEvidence:
        return AdapterRuntimeEvidence(package_available=True, heartbeat_at=datetime.now(timezone.utc))


def payload(**updates):
    base = dict(
        workspace_id="ws-a",
        source_key="source-1",
        actor_id="tester",
        pipeline_active=True,
        terminal_path_configured=True,
        credentials_reference_configured=True,
        requested_account_login=123456,
        allowed_account_logins=[123456],
        required_symbols=["XAUUSD", "EURUSD"],
        account_risk_approved=True,
        prop_rules_approved=True,
        human_approved=True,
    )
    base.update(updates)
    return NativeAdapterAssessmentCreate(**base)


def ready_evidence(**updates):
    base = dict(
        package_available=True,
        initialized=True,
        logged_in=True,
        terminal_connected=True,
        trade_allowed=True,
        account_login=123456,
        account_server="Demo-Server",
        visible_symbols=["XAUUSD", "EURUSD"],
        heartbeat_at=datetime.now(timezone.utc),
    )
    base.update(updates)
    return AdapterRuntimeEvidence(**base)


def test_requires_pipeline_active():
    service = NativeAdapterRuntimeService(FakeAdapter(ready_evidence()))
    record = service.create(payload(pipeline_active=False))
    assert record.state == NativeAdapterState.PIPELINE_REQUIRED


def test_requires_configuration():
    service = NativeAdapterRuntimeService(FakeAdapter(ready_evidence()))
    record = service.create(payload(terminal_path_configured=False))
    assert record.state == NativeAdapterState.CONFIGURATION_INVALID


def test_rejects_account_outside_allowlist():
    service = NativeAdapterRuntimeService(FakeAdapter(ready_evidence()))
    record = service.create(payload(allowed_account_logins=[999999]))
    assert record.state == NativeAdapterState.ACCOUNT_MISMATCH


def test_requires_human_approval():
    service = NativeAdapterRuntimeService(FakeAdapter(ready_evidence()))
    record = service.create(payload(human_approved=False))
    assert record.state == NativeAdapterState.APPROVAL_REQUIRED


def test_package_unavailable():
    service = NativeAdapterRuntimeService(FakeAdapter(AdapterRuntimeEvidence(package_available=False)))
    record = service.create(payload())
    updated = service.execute(record.id, "ws-a", NativeAdapterExecuteRequest(actor_id="operator", action="connect"))
    assert updated.state == NativeAdapterState.PACKAGE_UNAVAILABLE


def test_initialization_pending():
    service = NativeAdapterRuntimeService(FakeAdapter(ready_evidence(initialized=False)))
    record = service.create(payload())
    updated = service.execute(record.id, "ws-a", NativeAdapterExecuteRequest(actor_id="operator", action="connect"))
    assert updated.state == NativeAdapterState.INITIALIZATION_PENDING


def test_login_pending():
    service = NativeAdapterRuntimeService(FakeAdapter(ready_evidence(logged_in=False, account_login=None)))
    record = service.create(payload())
    updated = service.execute(record.id, "ws-a", NativeAdapterExecuteRequest(actor_id="operator", action="connect"))
    assert updated.state == NativeAdapterState.LOGIN_PENDING


def test_connected_account_must_match():
    service = NativeAdapterRuntimeService(FakeAdapter(ready_evidence(account_login=654321)))
    record = service.create(payload())
    updated = service.execute(record.id, "ws-a", NativeAdapterExecuteRequest(actor_id="operator", action="connect"))
    assert updated.state == NativeAdapterState.ACCOUNT_MISMATCH


def test_terminal_must_allow_trading():
    service = NativeAdapterRuntimeService(FakeAdapter(ready_evidence(trade_allowed=False)))
    record = service.create(payload())
    updated = service.execute(record.id, "ws-a", NativeAdapterExecuteRequest(actor_id="operator", action="connect"))
    assert updated.state == NativeAdapterState.TERMINAL_UNHEALTHY


def test_required_symbols_must_be_visible():
    service = NativeAdapterRuntimeService(FakeAdapter(ready_evidence(visible_symbols=["XAUUSD"])))
    record = service.create(payload())
    updated = service.execute(record.id, "ws-a", NativeAdapterExecuteRequest(actor_id="operator", action="connect"))
    assert updated.state == NativeAdapterState.SYMBOL_SYNC_REQUIRED


def test_connect_becomes_adapter_ready():
    service = NativeAdapterRuntimeService(FakeAdapter(ready_evidence()))
    record = service.create(payload())
    updated = service.execute(record.id, "ws-a", NativeAdapterExecuteRequest(actor_id="operator", action="connect"))
    assert updated.state == NativeAdapterState.ADAPTER_READY


def test_disconnect_is_governed():
    service = NativeAdapterRuntimeService(FakeAdapter(ready_evidence()))
    record = service.create(payload())
    updated = service.execute(record.id, "ws-a", NativeAdapterExecuteRequest(actor_id="operator", action="disconnect"))
    assert updated.state == NativeAdapterState.DISCONNECTED


def test_risk_brain_hard_block():
    service = NativeAdapterRuntimeService(FakeAdapter(ready_evidence()))
    record = service.create(payload(risk_brain_blocked=True))
    assert record.state == NativeAdapterState.BLOCKED


def test_duplicate_source_key_rejected():
    service = NativeAdapterRuntimeService(FakeAdapter(ready_evidence()))
    service.create(payload())
    try:
        service.create(payload())
        assert False, "duplicate should fail"
    except ValueError:
        assert True


def test_workspace_isolation():
    service = NativeAdapterRuntimeService(FakeAdapter(ready_evidence()))
    record = service.create(payload())
    assert service.get(record.id, "ws-b") is None
    assert service.list_records("ws-b") == []
