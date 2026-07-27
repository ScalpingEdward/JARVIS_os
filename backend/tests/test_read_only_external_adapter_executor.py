import pytest

from app.schemas.read_only_external_adapter_executor import (
    ReadOnlyExecutionAction,
    ReadOnlyExecutionCreate,
    ReadOnlyExecutionResult,
)
from app.services.read_only_external_adapter_executor import ReadOnlyExternalAdapterExecutorService


def payload(**overrides):
    request = {
        "worker_record_id": "worker-001",
        "gateway_record_id": "gateway-001",
        "dispatch_token_digest": "sha256:dispatch-token",
        "worker_id": "worker-a",
        "adapter_id": "github-readonly-adapter",
        "tool_name": "github",
        "operation": "read-repository",
        "target_host": "api.github.com",
        "target_path": "/repos/ScalpingEdward/JARVIS_os",
        "method": "GET",
        "timeout_seconds": 20,
        "max_response_bytes": 1_048_576,
        "follow_redirects": False,
        "side_effect_level": "read-only",
    }
    request.update(overrides)
    return ReadOnlyExecutionCreate(
        workspace_id="ws-a",
        source_key="readonly-exec-001",
        requested_by="orchestrator",
        request=request,
        egress_allow_hosts=["api.github.com"],
        pinned_hosts=["api.github.com"],
        allowed_operations=["read-repository", "read-file", "list-pull-requests"],
    )


def action(name, op):
    return ReadOnlyExecutionAction(workspace_id="ws-a", action=name, actor="owner", operation_id=op)


def test_status_exposes_strict_read_only_boundary():
    status = ReadOnlyExternalAdapterExecutorService().status()
    assert status["version"] == "21.120"
    assert status["read_only_external_execution_enabled"] is True
    assert status["write_methods_enabled"] is False
    assert status["trading_execution_enabled"] is False
    assert status["host_pinning_required"] is True


def test_safe_execution_lifecycle_and_receipt():
    service = ReadOnlyExternalAdapterExecutorService()
    record = service.create(payload())
    assert record.state.value == "review-required"
    record = service.act(record.record_id, action("approve", "op-1"))
    record = service.act(record.record_id, action("authorize", "op-2"))
    record = service.act(record.record_id, action("prepare", "op-3"))
    record = service.act(record.record_id, action("start", "op-4"))
    result = ReadOnlyExecutionResult(
        workspace_id="ws-a", operation_id="op-5", worker_id="worker-a",
        adapter_id="github-readonly-adapter", status="succeeded", http_status=200,
        response_digest="sha256:response", response_bytes=512, duration_ms=20,
    )
    record = service.ingest_result(record.record_id, result)
    assert record.state.value == "succeeded"
    assert record.receipt_digest
    assert record.response_bytes == 512


def test_response_size_limit_is_enforced():
    service = ReadOnlyExternalAdapterExecutorService()
    record = service.create(payload(max_response_bytes=100))
    for name, op in [("approve", "op-1"), ("authorize", "op-2"), ("prepare", "op-3"), ("start", "op-4")]:
        record = service.act(record.record_id, action(name, op))
    result = ReadOnlyExecutionResult(
        workspace_id="ws-a", operation_id="op-5", worker_id="worker-a",
        adapter_id="github-readonly-adapter", status="succeeded",
        response_digest="sha256:too-big", response_bytes=101, duration_ms=10,
    )
    with pytest.raises(ValueError, match="response exceeds"):
        service.ingest_result(record.record_id, result)


def test_protected_operation_is_risk_brain_blocked():
    service = ReadOnlyExternalAdapterExecutorService()
    p = payload(operation="trade-execute")
    p.allowed_operations.append("trade-execute")
    record = service.create(p)
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_replay_and_workspace_isolation():
    service = ReadOnlyExternalAdapterExecutorService()
    record = service.create(payload())
    service.act(record.record_id, action("approve", "same-op"))
    with pytest.raises(ValueError, match="replay"):
        service.act(record.record_id, action("authorize", "same-op"))
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_rejected():
    service = ReadOnlyExternalAdapterExecutorService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
