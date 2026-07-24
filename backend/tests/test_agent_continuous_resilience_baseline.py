import pytest

from app.schemas.agent_continuous_resilience_baseline import AgentContinuousResilienceCreate
from app.services.agent_continuous_resilience_baseline import AgentContinuousResilienceBaselineService


def payload(**overrides):
    observation = {
        "agent_id": "phoenix-agent",
        "agent_version": "21.101",
        "baseline_id": "baseline-001",
        "availability_score": 0.98,
        "latency_stability_score": 0.98,
        "error_rate_stability_score": 0.98,
        "recovery_time_score": 0.98,
        "failover_stability_score": 0.98,
        "dependency_stability_score": 0.98,
        "observability_stability_score": 0.98,
        "control_effectiveness_score": 0.98,
        "recurrence_prevention_score": 0.98,
        "regression_coverage_score": 0.98,
        "confidence": 1.0,
        "freshness": 1.0,
        "business_criticality": 0.70,
    }
    observation.update(overrides)
    return AgentContinuousResilienceCreate(
        workspace_id="ws-a",
        source_key="resilience-source",
        requested_by="operator",
        observations=[observation],
    )


def test_status_is_governance_only():
    status = AgentContinuousResilienceBaselineService().status()
    assert status["version"] == "21.101"
    assert status["automatic_remediation_enabled"] is False
    assert status["automatic_baseline_mutation_enabled"] is False
    assert status["automatic_failover_enabled"] is False
    assert status["execution_enabled"] is False


def test_stable_record_can_be_approved():
    service = AgentContinuousResilienceBaselineService()
    record = service.create(payload())
    assert record.risk_flags == []
    record = service.act("ws-a", record.record_id, "assess", "reviewer", "op-1")
    record = service.act("ws-a", record.record_id, "submit-review", "reviewer", "op-2")
    record = service.act("ws-a", record.record_id, "approve", "human-owner", "op-3")
    assert record.approved_by == "human-owner"


def test_regression_findings_block_approval():
    service = AgentContinuousResilienceBaselineService()
    record = service.create(payload(regression_coverage_score=0.40, failed_regression_checks=1))
    assert any(flag.startswith("regression-alert") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "human-owner", "op-a")


def test_critical_recurrence_triggers_risk_brain_hard_block():
    service = AgentContinuousResilienceBaselineService()
    record = service.create(payload(
        business_criticality=0.98,
        repeated_incident_count=1,
        failed_regression_checks=1,
    ))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_operation_replay_is_rejected():
    service = AgentContinuousResilienceBaselineService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "assess", "reviewer", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "submit-review", "reviewer", "same-op")


def test_workspace_isolation():
    service = AgentContinuousResilienceBaselineService()
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = AgentContinuousResilienceBaselineService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
