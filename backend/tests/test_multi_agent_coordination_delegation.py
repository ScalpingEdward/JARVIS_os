import pytest

from app.schemas.multi_agent_coordination_delegation import MultiAgentCoordinationCreate
from app.services.multi_agent_coordination_delegation import MultiAgentCoordinationDelegationService


def _payload(**overrides):
    base = {
        "workspace_id": "workspace-a",
        "source_key": "coord-001",
        "requested_by": "risk-owner",
        "observations": [
            {
                "agent_id": "planner-agent",
                "agent_version": "1.0.0",
                "role": "planner",
                "authority_scope": 0.5,
                "responsibility_clarity": 0.95,
                "delegation_integrity": 0.96,
                "handoff_quality": 0.95,
                "consensus_alignment": 0.92,
                "conflict_resolution_readiness": 0.94,
                "shared_context_consistency": 0.96,
                "task_ownership_integrity": 0.95,
                "human_escalation_readiness": 1.0,
                "auditability_score": 1.0,
                "confidence": 0.95,
                "freshness": 1.0,
                "business_criticality": 0.7,
            },
            {
                "agent_id": "research-agent",
                "agent_version": "1.0.0",
                "role": "research",
                "authority_scope": 0.4,
                "responsibility_clarity": 0.95,
                "delegation_integrity": 0.95,
                "handoff_quality": 0.94,
                "consensus_alignment": 0.92,
                "conflict_resolution_readiness": 0.94,
                "shared_context_consistency": 0.95,
                "task_ownership_integrity": 0.96,
                "human_escalation_readiness": 1.0,
                "auditability_score": 1.0,
                "confidence": 0.95,
                "freshness": 1.0,
                "business_criticality": 0.6,
            },
        ],
    }
    base.update(overrides)
    return MultiAgentCoordinationCreate(**base)


def test_status_is_governance_only():
    service = MultiAgentCoordinationDelegationService()
    status = service.status()
    assert status["version"] == "21.90"
    assert status["agent_execution_enabled"] is False
    assert status["delegation_mutation_enabled"] is False
    assert status["task_assignment_mutation_enabled"] is False
    assert status["execution_enabled"] is False
    assert status["risk_brain_authoritative"] is True


def test_healthy_coordination_can_be_approved_and_activated():
    service = MultiAgentCoordinationDelegationService()
    record = service.create(_payload())
    assert record.risk_flags == []
    service.act("workspace-a", record.record_id, "assess", "owner", "op-1")
    service.act("workspace-a", record.record_id, "submit-review", "owner", "op-2")
    approved = service.act("workspace-a", record.record_id, "approve", "human-approver", "op-3")
    assert approved.approved_by == "human-approver"
    active = service.act("workspace-a", record.record_id, "activate", "human-approver", "op-4")
    assert active.state.value == "active"


def test_unauthorized_delegation_blocks_approval():
    service = MultiAgentCoordinationDelegationService()
    payload = _payload()
    payload.observations[0].unauthorized_delegations = 1
    record = service.create(payload)
    assert any(flag.startswith("delegation-alert:") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("workspace-a", record.record_id, "approve", "owner", "op-a")


def test_deadlock_on_critical_agent_hard_blocks():
    service = MultiAgentCoordinationDelegationService()
    payload = _payload()
    payload.observations[0].business_criticality = 0.95
    payload.observations[0].coordination_deadlocks = 2
    record = service.create(payload)
    assert record.state.value == "blocked"
    assert "risk-brain-hard-block" in record.risk_flags


def test_operation_replay_is_rejected():
    service = MultiAgentCoordinationDelegationService()
    record = service.create(_payload())
    service.act("workspace-a", record.record_id, "assess", "owner", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("workspace-a", record.record_id, "monitor", "owner", "same-op")


def test_workspace_isolation():
    service = MultiAgentCoordinationDelegationService()
    record = service.create(_payload())
    with pytest.raises(KeyError):
        service.get("workspace-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = MultiAgentCoordinationDelegationService()
    service.create(_payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(_payload())


def test_duplicate_agent_is_rejected():
    payload = _payload().model_dump()
    payload["source_key"] = "coord-dup"
    payload["observations"][1]["agent_id"] = payload["observations"][0]["agent_id"]
    with pytest.raises(ValueError, match="duplicate agent observation"):
        MultiAgentCoordinationCreate(**payload)
