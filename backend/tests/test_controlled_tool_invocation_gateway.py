import pytest

from app.schemas.controlled_tool_invocation_gateway import ToolInvocationCreate, ToolInvocationResult
from app.services.controlled_tool_invocation_gateway import ControlledToolInvocationGatewayService


def payload(*, allowed_operations=None, **overrides):
    invocation = {
        "agent_id": "phoenix-agent",
        "task_id": "task-001",
        "sandbox_record_id": "sandbox-001",
        "adapter_id": "github-adapter",
        "tool_name": "github",
        "operation": "read-repository",
        "permission_scopes": ["repo:read"],
        "data_domains": ["source-code"],
        "target_host": "api.github.com",
        "arguments": {"repository": "ScalpingEdward/JARVIS_os"},
        "timeout_seconds": 30,
        "estimated_cost": 0.0,
        "side_effect_level": "read-only",
        "human_approval_required": True,
        "dry_run_verified": True,
    }
    invocation.update(overrides)
    return ToolInvocationCreate(
        workspace_id="ws-a",
        source_key="invoke-001",
        requested_by="planner",
        invocation=invocation,
        allowed_tools=["github"],
        allowed_operations=allowed_operations or ["read-repository", "create-draft-pr"],
        allowed_hosts=["api.github.com"],
        denied_operations=["delete-repository"],
    )


def test_status_reports_gateway_boundary():
    status = ControlledToolInvocationGatewayService().status()
    assert status["version"] == "21.118"
    assert status["gateway_enabled"] is True
    assert status["dispatch_contract_enabled"] is True
    assert status["embedded_external_network_invocation_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_safe_request_reaches_dispatch_ready_after_approval_and_authorization():
    service = ControlledToolInvocationGatewayService()
    record = service.create(payload())
    assert not record.risk_flags
    record = service.act("ws-a", record.record_id, "approve", "human-owner", "op-1")
    record = service.act("ws-a", record.record_id, "authorize", "security-owner", "op-2")
    record = service.act("ws-a", record.record_id, "prepare-dispatch", "gateway", "op-3")
    assert record.state.value == "dispatch-ready"
    assert record.dispatch_token


def test_result_requires_dispatched_state_and_matching_adapter():
    service = ControlledToolInvocationGatewayService()
    record = service.create(payload())
    record = service.act("ws-a", record.record_id, "approve", "human-owner", "op-1")
    record = service.act("ws-a", record.record_id, "authorize", "security-owner", "op-2")
    record = service.act("ws-a", record.record_id, "prepare-dispatch", "gateway", "op-3")
    record = service.act("ws-a", record.record_id, "mark-dispatched", "adapter-runtime", "op-4")
    result = ToolInvocationResult(
        workspace_id="ws-a", operation_id="result-1", adapter_id="github-adapter",
        status="succeeded", output_digest="sha256:abc", duration_ms=25, cost=0.0,
    )
    record = service.ingest_result(record.record_id, result)
    assert record.state.value == "succeeded"
    assert record.result_digest == "sha256:abc"


def test_protected_operation_is_hard_blocked():
    service = ControlledToolInvocationGatewayService()
    record = service.create(
        payload(
            operation="trade-execute",
            side_effect_level="critical",
            allowed_operations=["read-repository", "create-draft-pr", "trade-execute"],
        )
    )
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_unapproved_authorization_is_rejected():
    service = ControlledToolInvocationGatewayService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="human approval required"):
        service.act("ws-a", record.record_id, "authorize", "security-owner", "op-x")


def test_replay_and_workspace_isolation():
    service = ControlledToolInvocationGatewayService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "approve", "owner", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "authorize", "owner", "same-op")
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_rejected():
    service = ControlledToolInvocationGatewayService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
