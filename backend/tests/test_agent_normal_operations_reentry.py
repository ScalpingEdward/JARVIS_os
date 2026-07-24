import pytest

from app.schemas.agent_normal_operations_reentry import NormalOperationsReentryCreate
from app.services.agent_normal_operations_reentry import AgentNormalOperationsReentryService


def payload(**overrides):
    observation = {
        "agent_id": "phoenix-agent", "agent_version": "21.108", "stabilization_window_hours": 48,
        "service_health_stability": 0.98, "latency_stability": 0.98, "error_rate_stability": 0.98,
        "state_integrity": 0.99, "dependency_health": 0.98, "business_kpi_stability": 0.97,
        "error_budget_posture": 0.97, "alert_noise_quality": 0.96, "operational_owner_readiness": 0.99,
        "runbook_currency": 0.98, "handoff_completeness": 1.0, "residual_risk_acceptance": 0.98,
        "confidence": 1.0, "freshness": 1.0, "criticality": 0.70,
    }
    observation.update(overrides)
    return NormalOperationsReentryCreate(
        workspace_id="ws-a", source_key="reentry-source", requested_by="operator", observations=[observation]
    )


def test_status_is_governance_only():
    status = AgentNormalOperationsReentryService().status()
    assert status["version"] == "21.108"
    assert status["hypercare_exit_execution_enabled"] is False
    assert status["traffic_shift_enabled"] is False
    assert status["runtime_restart_enabled"] is False
    assert status["agent_execution_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_healthy_record_can_enter_normal_operations_after_human_approval():
    service = AgentNormalOperationsReentryService()
    record = service.create(payload())
    assert not record.risk_flags
    record = service.act("ws-a", record.record_id, "assess", "reviewer", "op-1")
    record = service.act("ws-a", record.record_id, "submit-review", "reviewer", "op-2")
    record = service.act("ws-a", record.record_id, "approve", "owner", "op-3")
    record = service.act("ws-a", record.record_id, "enter-normal-operations", "owner", "op-4")
    assert record.state.value == "normal-operations"
    assert record.approved_by == "owner"


def test_reopened_incident_blocks_approval():
    service = AgentNormalOperationsReentryService()
    record = service.create(payload(reopened_incidents=1))
    assert any(flag.startswith("stability-alert") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "owner", "op-a")


def test_critical_unresolved_finding_hard_blocks():
    service = AgentNormalOperationsReentryService()
    record = service.create(payload(criticality=0.98, unresolved_high_findings=1))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_operation_replay_is_rejected():
    service = AgentNormalOperationsReentryService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "assess", "reviewer", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "submit-review", "reviewer", "same-op")


def test_workspace_isolation():
    service = AgentNormalOperationsReentryService()
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = AgentNormalOperationsReentryService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
