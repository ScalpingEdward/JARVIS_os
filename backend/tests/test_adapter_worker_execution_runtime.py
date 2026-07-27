import pytest

from app.schemas.adapter_worker_execution_runtime import (
    AdapterWorkerExecutionCreate,
    AdapterWorkerHeartbeat,
    AdapterWorkerLeaseRequest,
    AdapterWorkerResult,
)
from app.services.adapter_worker_execution_runtime import AdapterWorkerExecutionRuntimeService


def payload(**overrides):
    data = {
        "workspace_id": "ws-a",
        "source_key": "worker-001",
        "requested_by": "gateway",
        "gateway_record_id": "gateway-001",
        "dispatch_token": "dispatch-token-abcdefghijklmnopqrstuvwxyz",
        "adapter_id": "github-adapter",
        "tool_name": "github",
        "operation": "read-repository",
        "side_effect_level": "read-only",
    }
    data.update(overrides)
    return AdapterWorkerExecutionCreate(**data)


def test_status_reports_runtime_boundary():
    status = AdapterWorkerExecutionRuntimeService().status()
    assert status["version"] == "21.119"
    assert status["worker_runtime_enabled"] is True
    assert status["lease_heartbeat_enabled"] is True
    assert status["external_adapter_execution_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_safe_record_can_be_leased_and_heartbeat_moves_running():
    service = AdapterWorkerExecutionRuntimeService()
    record = service.create(payload())
    assert record.state.value == "pending"
    record = service.lease(record.record_id, AdapterWorkerLeaseRequest(workspace_id="ws-a", worker_id="worker-1", operation_id="op-1"))
    assert record.state.value == "leased"
    assert record.lease_token
    record = service.heartbeat(
        record.record_id,
        AdapterWorkerHeartbeat(workspace_id="ws-a", worker_id="worker-1", lease_token=record.lease_token, operation_id="op-2"),
    )
    assert record.state.value == "running"


def test_result_requires_matching_worker_and_lease():
    service = AdapterWorkerExecutionRuntimeService()
    record = service.create(payload())
    record = service.lease(record.record_id, AdapterWorkerLeaseRequest(workspace_id="ws-a", worker_id="worker-1", operation_id="op-1"))
    with pytest.raises(ValueError, match="worker identity mismatch"):
        service.ingest_result(
            record.record_id,
            AdapterWorkerResult(
                workspace_id="ws-a", worker_id="worker-2", lease_token=record.lease_token,
                operation_id="result-x", status="succeeded", output_digest="sha256:abc", duration_ms=20, cost=0.0,
            ),
        )


def test_successful_result_closes_runtime_record():
    service = AdapterWorkerExecutionRuntimeService()
    record = service.create(payload())
    record = service.lease(record.record_id, AdapterWorkerLeaseRequest(workspace_id="ws-a", worker_id="worker-1", operation_id="op-1"))
    record = service.ingest_result(
        record.record_id,
        AdapterWorkerResult(
            workspace_id="ws-a", worker_id="worker-1", lease_token=record.lease_token,
            operation_id="result-1", status="succeeded", output_digest="sha256:abc", duration_ms=20, cost=0.0,
        ),
    )
    assert record.state.value == "succeeded"
    assert record.result_digest == "sha256:abc"


def test_protected_operation_is_risk_brain_hard_blocked():
    service = AdapterWorkerExecutionRuntimeService()
    record = service.create(payload(operation="trade-execute", side_effect_level="critical"))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_replay_and_workspace_isolation():
    service = AdapterWorkerExecutionRuntimeService()
    record = service.create(payload())
    service.lease(record.record_id, AdapterWorkerLeaseRequest(workspace_id="ws-a", worker_id="worker-1", operation_id="same-op"))
    with pytest.raises(ValueError, match="replay"):
        service.heartbeat(
            record.record_id,
            AdapterWorkerHeartbeat(workspace_id="ws-a", worker_id="worker-1", lease_token=service.get("ws-a", record.record_id).lease_token, operation_id="same-op"),
        )
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_rejected():
    service = AdapterWorkerExecutionRuntimeService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
