import pytest

from app.schemas.tool_execution_sandbox import ToolExecutionRequest, ToolExecutionResult
from app.services.tool_execution_sandbox import ToolExecutionSandboxService


def payload(**overrides):
    data = {
        "workspace_id": "ws-a",
        "source_key": "sandbox-source",
        "requested_by": "planner",
        "agent_id": "phoenix-agent",
        "task_id": "task-1",
        "tool_name": "github",
        "operation": "read-repository",
        "allowed_operations": ["read-repository"],
        "permission_scopes": ["repo:read"],
        "side_effect_level": "none",
        "timeout_seconds": 30,
        "max_calls": 3,
        "budget_units": 5,
        "requires_human_approval": True,
        "dry_run": True,
        "kill_switch_armed": True,
        "confidence": 0.98,
    }
    data.update(overrides)
    return ToolExecutionRequest(**data)


def test_status_keeps_external_execution_disabled():
    status = ToolExecutionSandboxService().status()
    assert status["version"] == "21.116"
    assert status["sandbox_enabled"] is True
    assert status["external_adapter_execution_enabled"] is False
    assert status["trading_execution_enabled"] is False
    assert status["fund_movement_enabled"] is False


def test_approved_dry_run_reaches_running_and_receipt():
    service = ToolExecutionSandboxService()
    record = service.create(payload())
    record = service.act("ws-a", record.record_id, "approve", "human", "op-1")
    record = service.act("ws-a", record.record_id, "authorize", "human", "op-2")
    record = service.act("ws-a", record.record_id, "start", "orchestrator", "op-3")
    assert record.state.value == "running"
    assert record.receipt is not None
    assert record.receipt.dry_run is True


def test_result_enforces_budget_and_call_limit():
    service = ToolExecutionSandboxService()
    record = service.create(payload())
    record = service.act("ws-a", record.record_id, "approve", "human", "op-1")
    record = service.act("ws-a", record.record_id, "authorize", "human", "op-2")
    record = service.act("ws-a", record.record_id, "start", "orchestrator", "op-3")
    with pytest.raises(ValueError, match="call limit"):
        service.record_result(record.record_id, ToolExecutionResult(workspace_id="ws-a", operation_id="op-4", status="succeeded", call_count=4, budget_used=1))


def test_external_side_effect_execution_stays_disabled():
    service = ToolExecutionSandboxService()
    record = service.create(payload(dry_run=False))
    record = service.act("ws-a", record.record_id, "approve", "human", "op-1")
    record = service.act("ws-a", record.record_id, "authorize", "human", "op-2")
    with pytest.raises(ValueError, match="external adapter execution"):
        service.act("ws-a", record.record_id, "start", "orchestrator", "op-3")


def test_forbidden_operation_is_risk_brain_blocked():
    service = ToolExecutionSandboxService()
    record = service.create(payload(operation="execute-trade", allowed_operations=["execute-trade"], side_effect_level="critical", confidence=0.95))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_replay_and_workspace_isolation():
    service = ToolExecutionSandboxService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "approve", "human", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "authorize", "human", "same-op")
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_rejected():
    service = ToolExecutionSandboxService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
