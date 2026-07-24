import pytest

from app.schemas.agent_objective_intent_alignment import AgentObjectiveCreate
from app.services.agent_objective_intent_alignment import AgentObjectiveIntentAlignmentService


def _payload(**overrides):
    observation = {
        "agent_id": "planner-agent-1",
        "agent_version": "1.0.0",
        "objective_id": "portfolio-analysis",
        "declared_objective_alignment": 0.96,
        "instruction_hierarchy_integrity": 0.98,
        "constraint_compliance": 0.99,
        "priority_consistency": 0.95,
        "human_intent_alignment": 0.97,
        "policy_intent_alignment": 0.98,
        "cross_agent_goal_consistency": 0.94,
        "goal_stability": 0.95,
        "explainability_score": 0.92,
        "confidence": 0.96,
        "freshness": 1.0,
        "objective_drift_events": 0,
        "conflicting_instruction_events": 0,
        "constraint_breach_events": 0,
        "priority_inversion_events": 0,
        "suspected_goal_hijack_events": 0,
        "business_criticality": 0.70,
    }
    observation.update(overrides.pop("observation", {}))
    payload = {
        "workspace_id": "workspace-a",
        "source_key": "objective-alignment-001",
        "requested_by": "risk-owner",
        "observations": [observation],
    }
    payload.update(overrides)
    return AgentObjectiveCreate(**payload)


def test_status_is_advisory_only():
    service = AgentObjectiveIntentAlignmentService()
    status = service.status()
    assert status["version"] == "21.91"
    assert status["objective_mutation_enabled"] is False
    assert status["instruction_mutation_enabled"] is False
    assert status["automatic_reprioritization_enabled"] is False
    assert status["agent_execution_enabled"] is False
    assert status["execution_enabled"] is False
    assert status["risk_brain_authoritative"] is True


def test_aligned_objective_can_be_approved_and_activated():
    service = AgentObjectiveIntentAlignmentService()
    record = service.create(_payload())
    assert record.risk_flags == []
    service.act("workspace-a", record.record_id, "assess", "owner", "op-1")
    service.act("workspace-a", record.record_id, "submit-review", "owner", "op-2")
    approved = service.act("workspace-a", record.record_id, "approve", "human-approver", "op-3")
    assert approved.approved_by == "human-approver"
    active = service.act("workspace-a", record.record_id, "activate", "human-approver", "op-4")
    assert active.state.value == "active"


def test_objective_drift_blocks_approval():
    service = AgentObjectiveIntentAlignmentService()
    record = service.create(_payload(observation={"objective_drift_events": 2, "declared_objective_alignment": 0.60}))
    assert any(flag.startswith("objective-drift:") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("workspace-a", record.record_id, "approve", "owner", "op-drift")


def test_goal_hijack_on_critical_agent_hard_blocks():
    service = AgentObjectiveIntentAlignmentService()
    record = service.create(_payload(observation={"business_criticality": 0.95, "suspected_goal_hijack_events": 1}))
    assert record.state.value == "blocked"
    assert "risk-brain-hard-block" in record.risk_flags


def test_constraint_breach_is_flagged():
    service = AgentObjectiveIntentAlignmentService()
    record = service.create(_payload(observation={"constraint_breach_events": 1, "constraint_compliance": 0.70}))
    assert any(flag.startswith("constraint-alert:") for flag in record.risk_flags)


def test_operation_replay_is_rejected():
    service = AgentObjectiveIntentAlignmentService()
    record = service.create(_payload())
    service.act("workspace-a", record.record_id, "assess", "owner", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("workspace-a", record.record_id, "monitor", "owner", "same-op")


def test_workspace_isolation():
    service = AgentObjectiveIntentAlignmentService()
    record = service.create(_payload())
    with pytest.raises(KeyError):
        service.get("workspace-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = AgentObjectiveIntentAlignmentService()
    service.create(_payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(_payload())


def test_duplicate_agent_objective_pair_is_rejected():
    base = _payload().model_dump()
    base["source_key"] = "objective-alignment-dup"
    base["observations"] = [base["observations"][0], base["observations"][0]]
    with pytest.raises(ValueError, match="duplicate agent/objective observation"):
        AgentObjectiveCreate(**base)
