import pytest

from app.schemas.agent_capability_registry import CapabilityMatchRequest, CapabilityRegistryCreate
from app.services.agent_capability_registry import AgentCapabilityRegistryService


def payload(**overrides):
    profile = {
        "agent_id": "planner-agent",
        "agent_version": "21.113",
        "role": "planner",
        "capabilities": ["task-decomposition", "dependency-planning", "risk-aware-planning"],
        "tool_grants": [
            {
                "tool_name": "github-read",
                "permissions": ["repository:read"],
                "read_only": True,
                "requires_human_approval": False,
                "max_calls_per_task": 50,
            }
        ],
        "allowed_data_domains": ["github", "project-metadata"],
        "denied_actions": ["fund-movement", "order-execution", "credential-mutation"],
        "max_parallel_tasks": 4,
        "task_timeout_seconds": 900,
        "daily_budget_units": 100,
        "confidence_floor": 0.85,
        "criticality": 0.70,
        "human_owner": "operator",
    }
    profile.update(overrides)
    return CapabilityRegistryCreate(
        workspace_id="ws-a",
        source_key="planner-v1",
        requested_by="operator",
        profile=profile,
    )


def activate(service, record):
    record = service.act("ws-a", record.record_id, "submit-review", "reviewer", "op-1")
    record = service.act("ws-a", record.record_id, "approve", "owner", "op-2")
    return service.act("ws-a", record.record_id, "activate", "owner", "op-3")


def test_status_disables_execution_and_mutation():
    status = AgentCapabilityRegistryService().status()
    assert status["version"] == "21.113"
    assert status["task_execution_enabled"] is False
    assert status["tool_execution_enabled"] is False
    assert status["permission_mutation_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_safe_profile_can_be_approved_and_activated():
    service = AgentCapabilityRegistryService()
    record = service.create(payload())
    assert not record.risk_flags
    record = activate(service, record)
    assert record.state.value == "active"
    assert record.approved_by == "owner"


def test_mutable_tool_without_approval_blocks_approval():
    service = AgentCapabilityRegistryService()
    record = service.create(payload(tool_grants=[{
        "tool_name": "github-write",
        "permissions": ["repository:write"],
        "read_only": False,
        "requires_human_approval": False,
        "max_calls_per_task": 20,
    }]))
    assert any(flag.startswith("mutable-tool-without-human-approval") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "owner", "op-x")


def test_critical_low_confidence_profile_hard_blocks():
    service = AgentCapabilityRegistryService()
    record = service.create(payload(criticality=0.98, confidence_floor=0.55))
    assert "risk-brain-hard-block" in record.risk_flags


def test_capability_matching_requires_active_profile():
    service = AgentCapabilityRegistryService()
    record = service.create(payload())
    request = CapabilityMatchRequest(
        workspace_id="ws-a",
        required_capabilities=["task-decomposition"],
        required_tools=["github-read"],
        data_domains=["github"],
        minimum_confidence=0.80,
    )
    assert service.match(request) == []
    activate(service, record)
    results = service.match(request)
    assert len(results) == 1
    assert results[0].eligible is True


def test_missing_capability_is_reported():
    service = AgentCapabilityRegistryService()
    record = service.create(payload())
    activate(service, record)
    results = service.match(CapabilityMatchRequest(
        workspace_id="ws-a",
        required_capabilities=["browser-navigation"],
    ))
    assert results[0].eligible is False
    assert "missing-required-capability" in results[0].reasons


def test_replay_and_workspace_isolation():
    service = AgentCapabilityRegistryService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "submit-review", "reviewer", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "approve", "owner", "same-op")
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_rejected():
    service = AgentCapabilityRegistryService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
