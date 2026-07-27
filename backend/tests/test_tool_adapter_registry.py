import pytest

from app.schemas.tool_adapter_registry import ToolAdapterMatchRequest, ToolAdapterRegistryCreate
from app.services.tool_adapter_registry import ToolAdapterRegistryService


def payload(**overrides):
    adapter = {
        "adapter_id": "github-adapter",
        "adapter_version": "1.0",
        "connector_type": "github",
        "supported_tools": ["repo.read", "pr.read"],
        "supported_operations": ["fetch", "search"],
        "permission_scopes": ["repo:read"],
        "data_domains": ["source-code"],
        "side_effect_level": "read-only",
        "requires_human_approval": True,
        "health_score": 0.99,
        "reliability_score": 0.99,
    }
    adapter.update(overrides)
    return ToolAdapterRegistryCreate(
        workspace_id="ws-a", source_key="adapter-source", requested_by="operator", adapter=adapter
    )


def test_status_keeps_external_execution_disabled():
    status = ToolAdapterRegistryService().status()
    assert status["version"] == "21.117"
    assert status["registry_enabled"] is True
    assert status["adapter_matching_enabled"] is True
    assert status["connector_invocation_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_adapter_can_be_approved_and_activated():
    service = ToolAdapterRegistryService()
    record = service.create(payload())
    assert not record.risk_flags
    record = service.act("ws-a", record.record_id, "approve", "owner", "op-1")
    record = service.act("ws-a", record.record_id, "activate", "owner", "op-2")
    assert record.state.value == "active"


def test_matching_requires_active_adapter_and_full_coverage():
    service = ToolAdapterRegistryService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "approve", "owner", "op-1")
    service.act("ws-a", record.record_id, "activate", "owner", "op-2")
    matches = service.match(ToolAdapterMatchRequest(
        workspace_id="ws-a", tool="repo.read", operation="fetch",
        permission_scopes=["repo:read"], data_domain="source-code",
    ))
    assert matches[0].eligible is True


def test_mutable_adapter_without_approval_is_flagged():
    service = ToolAdapterRegistryService()
    record = service.create(payload(side_effect_level="mutable", requires_human_approval=False))
    assert "mutable-adapter-without-human-approval" in record.risk_flags
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "owner", "op-a")


def test_protected_operation_triggers_risk_brain_hard_block():
    service = ToolAdapterRegistryService()
    record = service.create(payload(supported_operations=["fetch", "trade-execute"]))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_operation_replay_and_workspace_isolation():
    service = ToolAdapterRegistryService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "approve", "owner", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "activate", "owner", "same-op")
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = ToolAdapterRegistryService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
