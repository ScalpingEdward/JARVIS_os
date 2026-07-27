import pytest

from app.schemas.one_time_permit_dispatch_reconciliation import DispatchHandoffCreate, DispatchReceipt
from app.services.one_time_permit_dispatch_reconciliation import OneTimePermitDispatchReconciliationService


def payload(**overrides):
    data = {
        "workspace_id": "ws-a",
        "source_key": "handoff-1",
        "requested_by": "operator",
        "permit_id": "permit-1",
        "permit_token_digest": "a" * 64,
        "authorization_chain_record_id": "chain-1",
        "authorization_chain_digest": "b" * 64,
        "gateway_record_id": "gateway-1",
        "gateway_dispatch_token_digest": "c" * 64,
        "worker_record_id": "worker-1",
        "adapter_id": "adapter-1",
        "operation": "read-status",
        "target": "https://example.com/status",
        "method": "GET",
        "human_approved": True,
        "permit_eligible": True,
        "permit_issued": True,
    }
    data.update(overrides)
    return DispatchHandoffCreate(**data)


def receipt(**overrides):
    data = {
        "workspace_id": "ws-a",
        "permit_id": "permit-1",
        "permit_token_digest": "a" * 64,
        "authorization_chain_digest": "b" * 64,
        "gateway_dispatch_token_digest": "c" * 64,
        "worker_record_id": "worker-1",
        "adapter_id": "adapter-1",
        "operation": "read-status",
        "target": "https://example.com/status",
        "status_code": 200,
        "response_digest": "d" * 64,
        "receipt_digest": "e" * 64,
        "duration_ms": 42,
        "response_bytes": 512,
    }
    data.update(overrides)
    return DispatchReceipt(**data)


def ready_for_receipt(service):
    record = service.create(payload())
    record = service.act("ws-a", record.record_id, "approve", "owner", "op-1")
    record = service.act("ws-a", record.record_id, "prepare-handoff", "owner", "op-2")
    record = service.act("ws-a", record.record_id, "consume-permit", "owner", "op-3")
    return service.act("ws-a", record.record_id, "mark-dispatched", "worker", "op-4")


def test_status_is_read_only_and_no_trading_execution():
    status = OneTimePermitDispatchReconciliationService().status()
    assert status["version"] == "21.130"
    assert status["read_only_only"] is True
    assert status["direct_network_client_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_complete_handoff_and_receipt_reconciliation():
    service = OneTimePermitDispatchReconciliationService()
    record = ready_for_receipt(service)
    record = service.reconcile(record.record_id, receipt())
    assert record.state.value == "reconciled"
    assert record.reconciliation_digest
    assert record.mismatch_reasons == []


def test_single_use_permit_cannot_be_consumed_twice():
    service = OneTimePermitDispatchReconciliationService()
    record = service.create(payload())
    record = service.act("ws-a", record.record_id, "approve", "owner", "op-1")
    record = service.act("ws-a", record.record_id, "prepare-handoff", "owner", "op-2")
    service.act("ws-a", record.record_id, "consume-permit", "owner", "op-3")
    with pytest.raises(ValueError):
        service.act("ws-a", record.record_id, "consume-permit", "owner", "op-4")


def test_receipt_binding_mismatch_fails_closed():
    service = OneTimePermitDispatchReconciliationService()
    record = ready_for_receipt(service)
    record = service.reconcile(record.record_id, receipt(worker_record_id="worker-other"))
    assert record.state.value == "mismatch"
    assert "worker_record_id" in record.mismatch_reasons
    assert "receipt-binding-mismatch" in record.risk_flags


def test_protected_operation_hard_blocks():
    service = OneTimePermitDispatchReconciliationService()
    record = service.create(payload(operation="trade-execute"))
    assert record.state.value == "blocked"
    assert "risk-brain-hard-block" in record.risk_flags
    with pytest.raises(ValueError, match="hard block"):
        service.act("ws-a", record.record_id, "approve", "owner", "op-x")


def test_write_method_hard_blocks():
    service = OneTimePermitDispatchReconciliationService()
    record = service.create(payload(method="POST"))
    assert record.state.value == "blocked"
    assert "write-method-prohibited" in record.risk_flags


def test_replay_and_workspace_isolation():
    service = OneTimePermitDispatchReconciliationService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "approve", "owner", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "prepare-handoff", "owner", "same-op")
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_rejected():
    service = OneTimePermitDispatchReconciliationService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
