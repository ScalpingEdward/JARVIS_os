import pytest

from app.schemas.agent_decision_explainability_accountability import AgentDecisionAccountabilityCreate
from app.services.agent_decision_explainability_accountability import AgentDecisionExplainabilityAccountabilityService


def _payload(**overrides):
    observation = {
        "agent_id": "decision-agent-1",
        "decision_id": "decision-001",
        "decision_type": "portfolio-recommendation",
        "rationale_completeness": 0.95,
        "evidence_coverage": 0.95,
        "source_traceability": 0.98,
        "counterfactual_quality": 0.90,
        "uncertainty_disclosure": 0.95,
        "policy_reference_coverage": 0.95,
        "human_owner_coverage": 1.0,
        "reviewability_score": 0.95,
        "override_traceability": 1.0,
        "reproducibility_score": 0.95,
        "confidence": 0.95,
        "freshness": 1.0,
        "missing_evidence_count": 0,
        "untraceable_sources": 0,
        "undocumented_overrides": 0,
        "unresolved_challenges": 0,
        "business_criticality": 0.60,
    }
    observation.update(overrides.pop("observation", {}))
    payload = {
        "workspace_id": "workspace-a",
        "source_key": "decision-accountability-001",
        "requested_by": "risk-owner",
        "observations": [observation],
    }
    payload.update(overrides)
    return AgentDecisionAccountabilityCreate(**payload)


def test_status_is_advisory_only():
    service = AgentDecisionExplainabilityAccountabilityService()
    status = service.status()
    assert status["version"] == "21.92"
    assert status["decision_mutation_enabled"] is False
    assert status["automatic_override_enabled"] is False
    assert status["agent_execution_enabled"] is False
    assert status["execution_enabled"] is False
    assert status["risk_brain_authoritative"] is True


def test_healthy_decision_can_be_approved_and_activated():
    service = AgentDecisionExplainabilityAccountabilityService()
    record = service.create(_payload())
    assert record.risk_flags == []
    service.act("workspace-a", record.record_id, "assess", "owner", "op-1")
    service.act("workspace-a", record.record_id, "submit-review", "owner", "op-2")
    approved = service.act("workspace-a", record.record_id, "approve", "human-approver", "op-3")
    assert approved.approved_by == "human-approver"
    active = service.act("workspace-a", record.record_id, "activate", "human-approver", "op-4")
    assert active.state.value == "active"


def test_rationale_gap_blocks_approval():
    service = AgentDecisionExplainabilityAccountabilityService()
    record = service.create(_payload(observation={"rationale_completeness": 0.40}))
    assert any(flag.startswith("rationale-gap:") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("workspace-a", record.record_id, "approve", "owner", "op-a")


def test_untraceable_critical_decision_hard_blocks():
    service = AgentDecisionExplainabilityAccountabilityService()
    record = service.create(_payload(observation={"business_criticality": 0.95, "untraceable_sources": 1}))
    assert record.state.value == "blocked"
    assert "risk-brain-hard-block" in record.risk_flags


def test_undocumented_override_is_flagged():
    service = AgentDecisionExplainabilityAccountabilityService()
    record = service.create(_payload(observation={"undocumented_overrides": 1}))
    assert any(flag.startswith("override-alert:") for flag in record.risk_flags)


def test_operation_replay_is_rejected():
    service = AgentDecisionExplainabilityAccountabilityService()
    record = service.create(_payload())
    service.act("workspace-a", record.record_id, "assess", "owner", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("workspace-a", record.record_id, "monitor", "owner", "same-op")


def test_workspace_isolation():
    service = AgentDecisionExplainabilityAccountabilityService()
    record = service.create(_payload())
    with pytest.raises(KeyError):
        service.get("workspace-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = AgentDecisionExplainabilityAccountabilityService()
    service.create(_payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(_payload())
