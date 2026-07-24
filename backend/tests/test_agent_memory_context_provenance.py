import pytest

from app.schemas.agent_memory_context_provenance import AgentMemoryContextCreate
from app.services.agent_memory_context_provenance import AgentMemoryContextProvenanceService


def _payload(**overrides):
    observation = {
        "agent_id": "research-agent-1",
        "memory_id": "memory-001",
        "memory_type": "episodic",
        "source_authority": 0.95,
        "provenance_coverage": 1.0,
        "freshness_score": 0.95,
        "context_relevance": 0.95,
        "conflict_resolution_score": 0.95,
        "contamination_resilience": 0.95,
        "retention_compliance": 1.0,
        "sensitive_data_control": 0.95,
        "deletion_traceability": 1.0,
        "confidence": 0.95,
        "stale_reads": 0,
        "provenance_gaps": 0,
        "conflicting_memory_events": 0,
        "contamination_events": 0,
        "retention_breaches": 0,
        "sensitive_memory_events": 0,
        "business_criticality": 0.60,
    }
    observation.update(overrides.pop("observation", {}))
    payload = {
        "workspace_id": "workspace-a",
        "source_key": "memory-context-001",
        "requested_by": "risk-owner",
        "observations": [observation],
    }
    payload.update(overrides)
    return AgentMemoryContextCreate(**payload)


def test_status_is_advisory_only():
    service = AgentMemoryContextProvenanceService()
    status = service.status()
    assert status["version"] == "21.89"
    assert status["memory_mutation_enabled"] is False
    assert status["context_injection_enabled"] is False
    assert status["automatic_memory_deletion_enabled"] is False
    assert status["agent_execution_enabled"] is False
    assert status["execution_enabled"] is False
    assert status["risk_brain_authoritative"] is True


def test_healthy_memory_context_can_be_approved_and_activated():
    service = AgentMemoryContextProvenanceService()
    record = service.create(_payload())
    assert record.risk_flags == []
    service.act("workspace-a", record.record_id, "assess", "owner", "op-1")
    service.act("workspace-a", record.record_id, "submit-review", "owner", "op-2")
    approved = service.act("workspace-a", record.record_id, "approve", "human-approver", "op-3")
    assert approved.approved_by == "human-approver"
    active = service.act("workspace-a", record.record_id, "activate", "human-approver", "op-4")
    assert active.state.value == "active"


def test_provenance_gap_blocks_approval():
    service = AgentMemoryContextProvenanceService()
    record = service.create(_payload(observation={"provenance_gaps": 1}))
    assert any(flag.startswith("provenance-alert:") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("workspace-a", record.record_id, "approve", "owner", "op-a")


def test_contamination_is_flagged():
    service = AgentMemoryContextProvenanceService()
    record = service.create(_payload(observation={"contamination_events": 1}))
    assert any(flag.startswith("contamination-alert:") for flag in record.risk_flags)
    assert record.dispositions[0].lifecycle_signal == "contamination-alert"


def test_sensitive_memory_on_critical_agent_hard_blocks():
    service = AgentMemoryContextProvenanceService()
    record = service.create(_payload(observation={"business_criticality": 0.95, "sensitive_memory_events": 1}))
    assert record.state.value == "blocked"
    assert "risk-brain-hard-block" in record.risk_flags


def test_operation_replay_is_rejected():
    service = AgentMemoryContextProvenanceService()
    record = service.create(_payload())
    service.act("workspace-a", record.record_id, "assess", "owner", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("workspace-a", record.record_id, "monitor", "owner", "same-op")


def test_workspace_isolation():
    service = AgentMemoryContextProvenanceService()
    record = service.create(_payload())
    with pytest.raises(KeyError):
        service.get("workspace-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = AgentMemoryContextProvenanceService()
    service.create(_payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(_payload())


def test_duplicate_agent_memory_pair_is_rejected():
    base = _payload().model_dump()
    base["source_key"] = "memory-context-dup"
    base["observations"] = [base["observations"][0], base["observations"][0]]
    with pytest.raises(ValueError, match="duplicate agent/memory observation"):
        AgentMemoryContextCreate(**base)
