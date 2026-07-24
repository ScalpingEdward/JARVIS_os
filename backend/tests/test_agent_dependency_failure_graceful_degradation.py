import pytest

from app.schemas.agent_dependency_failure_graceful_degradation import DependencyFailureCreate
from app.services.agent_dependency_failure_graceful_degradation import AgentDependencyFailureGracefulDegradationService


def payload(**overrides):
    observation = {
        "agent_id": "phoenix-agent",
        "agent_version": "21.103",
        "dependency_id": "market-data-primary",
        "dependency_criticality": 0.70,
        "redundancy_coverage": 0.98,
        "failover_readiness": 0.98,
        "fallback_quality": 0.96,
        "graceful_degradation_quality": 0.95,
        "data_integrity_preservation": 0.99,
        "state_consistency": 0.98,
        "recovery_readiness": 0.98,
        "recovery_point_assurance": 0.97,
        "observability_coverage": 0.98,
        "human_override_readiness": 1.0,
        "confidence": 1.0,
        "freshness": 1.0,
    }
    observation.update(overrides)
    return DependencyFailureCreate(
        workspace_id="ws-a",
        source_key="dependency-source",
        requested_by="operator",
        observations=[observation],
    )


def test_status_is_advisory_only():
    status = AgentDependencyFailureGracefulDegradationService().status()
    assert status["version"] == "21.103"
    assert status["fault_injection_enabled"] is False
    assert status["automatic_failover_enabled"] is False
    assert status["automatic_fallback_enabled"] is False
    assert status["automatic_recovery_enabled"] is False
    assert status["agent_execution_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_healthy_dependency_record_can_be_approved():
    service = AgentDependencyFailureGracefulDegradationService()
    record = service.create(payload())
    assert not record.risk_flags
    service.act("ws-a", record.record_id, "assess", "reviewer", "op-1")
    service.act("ws-a", record.record_id, "submit-review", "reviewer", "op-2")
    approved = service.act("ws-a", record.record_id, "approve", "owner", "op-3")
    assert approved.approved_by == "owner"


def test_failover_findings_block_approval():
    service = AgentDependencyFailureGracefulDegradationService()
    record = service.create(payload(failover_readiness=0.40, failed_failover_checks=1))
    assert any(flag.startswith("failover-alert") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "owner", "op-a")


def test_critical_integrity_failure_hard_blocks():
    service = AgentDependencyFailureGracefulDegradationService()
    record = service.create(payload(
        dependency_criticality=0.98,
        single_point_failures=1,
        failed_failover_checks=1,
        integrity_violations=1,
        data_integrity_preservation=0.30,
    ))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_replay_is_rejected():
    service = AgentDependencyFailureGracefulDegradationService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "assess", "reviewer", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "submit-review", "reviewer", "same-op")


def test_workspace_isolation():
    service = AgentDependencyFailureGracefulDegradationService()
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = AgentDependencyFailureGracefulDegradationService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
