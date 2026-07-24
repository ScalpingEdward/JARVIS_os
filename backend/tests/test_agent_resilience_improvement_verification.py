import pytest

from app.schemas.agent_resilience_improvement_verification import AgentResilienceImprovementCreate
from app.services.agent_resilience_improvement_verification import AgentResilienceImprovementVerificationService


def payload(**overrides):
    observation = {
        "agent_id": "phoenix-agent", "agent_version": "21.100", "improvement_id": "imp-001",
        "control_implementation_score": 0.98, "resilience_test_coverage": 0.98,
        "chaos_test_readiness": 0.95, "failover_validation_score": 0.98,
        "recovery_validation_score": 0.98, "observability_validation_score": 0.98,
        "dependency_resilience_score": 0.96, "regression_coverage": 0.98,
        "owner_accountability": 1.0, "evidence_quality": 0.98,
        "recurrence_prevention_confidence": 0.98, "confidence": 1.0, "freshness": 1.0,
        "business_criticality": 0.70,
    }
    observation.update(overrides)
    return AgentResilienceImprovementCreate(
        workspace_id="ws-a", source_key="improvement-source", requested_by="operator", observations=[observation]
    )


def test_status_is_governance_only():
    status = AgentResilienceImprovementVerificationService().status()
    assert status["version"] == "21.100"
    assert status["automatic_remediation_enabled"] is False
    assert status["automatic_chaos_execution_enabled"] is False
    assert status["automatic_failover_enabled"] is False
    assert status["deployment_execution_enabled"] is False
    assert status["execution_enabled"] is False


def test_clean_improvement_can_be_approved():
    service = AgentResilienceImprovementVerificationService()
    record = service.create(payload())
    assert record.risk_flags == []
    record = service.act("ws-a", record.record_id, "assess", "reviewer", "op-1")
    record = service.act("ws-a", record.record_id, "submit-review", "reviewer", "op-2")
    record = service.act("ws-a", record.record_id, "approve", "human-owner", "op-3")
    assert record.approved_by == "human-owner"


def test_control_gap_blocks_approval():
    service = AgentResilienceImprovementVerificationService()
    record = service.create(payload(control_implementation_score=0.40, unresolved_control_gaps=1))
    assert any(flag.startswith("control-alert") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "human-owner", "op-a")


def test_critical_repeat_failure_hard_blocks():
    service = AgentResilienceImprovementVerificationService()
    record = service.create(payload(
        business_criticality=0.98, failed_failover_tests=1, failed_recovery_tests=1,
        repeat_incident_count=1, unresolved_control_gaps=1,
    ))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_replay_and_workspace_isolation():
    service = AgentResilienceImprovementVerificationService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "assess", "reviewer", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "submit-review", "reviewer", "same-op")
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_rejected():
    service = AgentResilienceImprovementVerificationService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
