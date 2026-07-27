import pytest

from app.schemas.multi_agent_orchestrator import OrchestrationCreate
from app.services.multi_agent_orchestrator import MultiAgentOrchestratorService


def payload(**overrides):
    task = {
        "task_id": "task-1", "title": "Analyze signal quality",
        "required_capabilities": ["analysis"], "required_tools": ["market-data"],
        "required_data_domains": ["trading"], "validator_required": True,
    }
    agent = {
        "agent_id": "analyst-1", "agent_version": "1.0",
        "capabilities": ["analysis"], "tools": ["market-data"],
        "data_domains": ["trading"], "confidence": 0.95, "active": True,
    }
    task.update(overrides.pop("task", {}))
    agent.update(overrides.pop("agent", {}))
    return OrchestrationCreate(
        workspace_id="ws-a", source_key="orch-source", requested_by="operator",
        planner_record_id="plan-1", goal="Validate market signal", tasks=[task], agents=[agent],
        **overrides,
    )


def test_status_keeps_side_effects_disabled():
    status = MultiAgentOrchestratorService().status()
    assert status["version"] == "21.115"
    assert status["assignment_runtime_enabled"] is True
    assert status["agent_dispatch_enabled"] is False
    assert status["tool_execution_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_eligible_agent_is_bound():
    service = MultiAgentOrchestratorService()
    record = service.create(payload())
    assert record.assignments[0].agent_id == "analyst-1"
    assert record.assignments[0].eligible is True


def test_unassigned_task_blocks_approval():
    service = MultiAgentOrchestratorService()
    record = service.create(payload(agent={"capabilities": []}))
    assert any(flag.startswith("unassigned") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "owner", "op-1")


def test_human_approval_precedes_dispatch_preparation():
    service = MultiAgentOrchestratorService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="human approval"):
        service.act("ws-a", record.record_id, "prepare-dispatch", "owner", "op-a")
    record = service.act("ws-a", record.record_id, "approve", "owner", "op-b")
    record = service.act("ws-a", record.record_id, "prepare-dispatch", "owner", "op-c")
    assert record.state.value == "dispatch-ready"


def test_task_lifecycle_reaches_completed():
    service = MultiAgentOrchestratorService()
    record = service.create(payload())
    record = service.act("ws-a", record.record_id, "approve", "owner", "op-1")
    record = service.act("ws-a", record.record_id, "mark-running", "orchestrator", "op-2", "task-1")
    record = service.act("ws-a", record.record_id, "require-validation", "validator", "op-3", "task-1")
    record = service.act("ws-a", record.record_id, "complete-task", "validator", "op-4", "task-1")
    assert record.state.value == "completed"
    assert record.assignments[0].validator_status == "passed"


def test_replay_and_workspace_isolation():
    service = MultiAgentOrchestratorService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "submit-review", "reviewer", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "approve", "owner", "same-op")
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_is_rejected():
    service = MultiAgentOrchestratorService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
