import pytest

from app.schemas.agent_post_recovery_stabilization import PostRecoveryCreate
from app.services.agent_post_recovery_stabilization import AgentPostRecoveryStabilizationService


def payload(**overrides):
    observation = {
        "agent_id": "phoenix-agent", "agent_version": "21.107", "window_id": "hypercare-01",
        "service_health": 0.98, "latency_stability": 0.98, "error_rate_stability": 0.98,
        "state_integrity": 0.99, "dependency_health": 0.98, "observability_coverage": 0.99,
        "business_kpi_stability": 0.98, "rollback_readiness": 0.98, "human_oncall_readiness": 1.0,
        "confidence": 1.0, "freshness": 1.0, "error_budget_remaining": 0.85, "criticality": 0.70,
    }
    observation.update(overrides)
    return PostRecoveryCreate(
        workspace_id="ws-a", source_key="post-recovery-source", requested_by="operator", observations=[observation]
    )


def test_status_is_governance_only():
    status = AgentPostRecoveryStabilizationService().status()
    assert status["version"] == "21.107"
    assert status["traffic_shift_enabled"] is False
    assert status["automatic_rollback_enabled"] is False
    assert status["automatic_remediation_enabled"] is False
    assert status["agent_execution_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_healthy_record_can_be_approved_and_stabilized():
    service = AgentPostRecoveryStabilizationService()
    record = service.create(payload())
    assert not record.risk_flags
    record = service.act("ws-a", record.record_id, "assess", "reviewer", "op-1")
    record = service.act("ws-a", record.record_id, "submit-review", "reviewer", "op-2")
    record = service.act("ws-a", record.record_id, "approve", "owner", "op-3")
    record = service.act("ws-a", record.record_id, "stabilize", "owner", "op-4")
    assert record.state.value == "stable"


def test_reopened_incident_blocks_approval():
    service = AgentPostRecoveryStabilizationService()
    record = service.create(payload(reopened_incidents=1))
    assert any(flag.startswith("health-alert") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "owner", "op-a")


def test_critical_post_recovery_failure_hard_blocks():
    service = AgentPostRecoveryStabilizationService()
    record = service.create(payload(
        criticality=0.98, state_integrity=0.50, reopened_incidents=1, business_impact_events=1,
    ))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_operation_replay_rejected():
    service = AgentPostRecoveryStabilizationService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "assess", "reviewer", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "submit-review", "reviewer", "same-op")


def test_workspace_isolation():
    service = AgentPostRecoveryStabilizationService()
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_rejected():
    service = AgentPostRecoveryStabilizationService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
