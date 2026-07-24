import pytest

from app.schemas.agent_post_incident_recovery_resilience import AgentPostIncidentRecoveryCreate
from app.services.agent_post_incident_recovery_resilience import AgentPostIncidentRecoveryResilienceService


def payload(**overrides):
    observation = {
        "agent_id": "phoenix-agent", "agent_version": "21.99", "incident_id": "inc-001",
        "service_restoration_score": 0.99, "stability_validation_score": 0.98,
        "regression_validation_score": 0.98, "root_cause_confidence": 0.96,
        "corrective_action_coverage": 0.98, "preventive_control_coverage": 0.98,
        "resilience_test_coverage": 0.98, "observability_improvement_score": 0.97,
        "runbook_improvement_score": 0.97, "lessons_learned_closure": 0.98,
        "owner_accountability_coverage": 1.0, "confidence": 1.0, "freshness": 1.0,
        "business_criticality": 0.70,
    }
    observation.update(overrides)
    return AgentPostIncidentRecoveryCreate(
        workspace_id="ws-a", source_key="recovery-source", requested_by="operator", observations=[observation]
    )


def test_status_is_advisory_only():
    status = AgentPostIncidentRecoveryResilienceService().status()
    assert status["version"] == "21.99"
    assert status["automatic_remediation_enabled"] is False
    assert status["automatic_control_mutation_enabled"] is False
    assert status["automatic_redeployment_enabled"] is False
    assert status["agent_execution_enabled"] is False
    assert status["execution_enabled"] is False


def test_clean_recovery_can_be_approved():
    service = AgentPostIncidentRecoveryResilienceService()
    record = service.create(payload())
    assert not record.risk_flags
    record = service.act("ws-a", record.record_id, "assess", "reviewer", "op-1")
    record = service.act("ws-a", record.record_id, "submit-review", "reviewer", "op-2")
    record = service.act("ws-a", record.record_id, "approve", "human-owner", "op-3")
    assert record.approved_by == "human-owner"


def test_open_corrective_actions_block_approval():
    service = AgentPostIncidentRecoveryResilienceService()
    record = service.create(payload(open_corrective_actions=2, corrective_action_coverage=0.70))
    assert any(flag.startswith("control-gap") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "human-owner", "op-a")


def test_repeat_failures_can_hard_block_critical_agent():
    service = AgentPostIncidentRecoveryResilienceService()
    record = service.create(payload(business_criticality=0.98, repeated_failure_signals=2))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_replay_and_workspace_isolation():
    service = AgentPostIncidentRecoveryResilienceService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "assess", "reviewer", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "submit-review", "reviewer", "same-op")
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = AgentPostIncidentRecoveryResilienceService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
