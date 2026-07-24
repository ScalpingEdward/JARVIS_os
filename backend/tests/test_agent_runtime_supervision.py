import pytest

from app.schemas.agent_runtime_supervision import AgentRuntimeCreate
from app.services.agent_runtime_supervision import AgentRuntimeSupervisionService


def _payload(**overrides):
    observation = {
        "agent_id": "research-agent-1",
        "agent_version": "1.1.0",
        "runtime_id": "runtime-a",
        "heartbeat_health": 0.98,
        "behavioral_stability": 0.95,
        "policy_conformance": 0.98,
        "tool_success_rate": 0.96,
        "output_validation_rate": 0.95,
        "human_override_readiness": 1.0,
        "stop_control_readiness": 1.0,
        "resource_efficiency": 0.90,
        "budget_headroom": 0.65,
        "context_integrity": 0.96,
        "confidence": 0.95,
        "freshness": 1.0,
        "repeated_action_count": 1,
        "consecutive_tool_failures": 0,
        "policy_violation_count": 0,
        "human_override_failures": 0,
        "resource_spike_count": 0,
        "business_criticality": 0.60,
    }
    observation.update(overrides.pop("observation", {}))
    payload = {
        "workspace_id": "workspace-a",
        "source_key": "runtime-supervision-001",
        "requested_by": "runtime-owner",
        "observations": [observation],
    }
    payload.update(overrides)
    return AgentRuntimeCreate(**payload)


def test_status_is_governance_only():
    service = AgentRuntimeSupervisionService()
    status = service.status()
    assert status["version"] == "21.88"
    assert status["agent_execution_enabled"] is False
    assert status["automatic_agent_stop_enabled"] is False
    assert status["automatic_intervention_enabled"] is False
    assert status["execution_enabled"] is False
    assert status["risk_brain_authoritative"] is True


def test_healthy_runtime_can_be_approved_and_activated():
    service = AgentRuntimeSupervisionService()
    record = service.create(_payload())
    assert record.risk_flags == []
    service.act("workspace-a", record.record_id, "assess", "owner", "op-1")
    service.act("workspace-a", record.record_id, "submit-review", "owner", "op-2")
    approved = service.act("workspace-a", record.record_id, "approve", "human-approver", "op-3")
    assert approved.approved_by == "human-approver"
    active = service.act("workspace-a", record.record_id, "activate", "human-approver", "op-4")
    assert active.state.value == "active"


def test_behavior_drift_blocks_approval():
    service = AgentRuntimeSupervisionService()
    record = service.create(_payload(observation={"behavioral_stability": 0.50}))
    assert any(flag.startswith("behavior-drift:") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("workspace-a", record.record_id, "approve", "owner", "op-a")


def test_runaway_loop_is_flagged():
    service = AgentRuntimeSupervisionService()
    record = service.create(_payload(observation={"repeated_action_count": 20}))
    assert any(flag.startswith("loop-alert:") for flag in record.risk_flags)
    assert record.dispositions[0].lifecycle_signal == "loop-alert"


def test_tool_failure_is_flagged():
    service = AgentRuntimeSupervisionService()
    record = service.create(_payload(observation={"consecutive_tool_failures": 4}))
    assert any(flag.startswith("tool-failure-alert:") for flag in record.risk_flags)


def test_failed_human_override_on_critical_agent_hard_blocks():
    service = AgentRuntimeSupervisionService()
    record = service.create(
        _payload(observation={"business_criticality": 0.95, "human_override_failures": 1})
    )
    assert record.state.value == "blocked"
    assert "risk-brain-hard-block" in record.risk_flags


def test_operation_replay_is_rejected():
    service = AgentRuntimeSupervisionService()
    record = service.create(_payload())
    service.act("workspace-a", record.record_id, "assess", "owner", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("workspace-a", record.record_id, "monitor", "owner", "same-op")


def test_workspace_isolation():
    service = AgentRuntimeSupervisionService()
    record = service.create(_payload())
    with pytest.raises(KeyError):
        service.get("workspace-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = AgentRuntimeSupervisionService()
    service.create(_payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(_payload())


def test_duplicate_agent_runtime_pair_is_rejected():
    base = _payload().model_dump()
    base["source_key"] = "runtime-supervision-dup"
    base["observations"] = [base["observations"][0], base["observations"][0]]
    with pytest.raises(ValueError, match="duplicate agent/runtime observation"):
        AgentRuntimeCreate(**base)
