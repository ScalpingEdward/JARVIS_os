from app.schemas.agent_production_observability_slo import (
    AgentProductionObservabilityCreate,
    AgentProductionObservabilityObservation,
    AgentProductionObservabilityState,
)
from app.services.agent_production_observability_slo import AgentProductionObservabilitySLOService


def observation(**overrides):
    payload = dict(
        agent_id="jarvis-agent",
        agent_version="21.97",
        production_environment="prod-eu",
        availability_slo_attainment=0.99,
        latency_slo_attainment=0.98,
        error_rate_slo_attainment=0.99,
        telemetry_coverage=0.98,
        trace_coverage=0.95,
        log_quality=0.96,
        metric_quality=0.97,
        alert_precision=0.95,
        incident_detection_readiness=0.96,
        human_oncall_readiness=0.95,
        runbook_coverage=0.94,
        error_budget_remaining=0.80,
        behavioral_drift_score=0.05,
        decision_drift_score=0.04,
        confidence=0.98,
        freshness=0.99,
        business_criticality=0.90,
    )
    payload.update(overrides)
    return AgentProductionObservabilityObservation(**payload)


def create_payload(**overrides):
    payload = dict(
        workspace_id="workspace-a",
        source_key="prod-observability-001",
        requested_by="operator",
        observations=[observation()],
    )
    payload.update(overrides)
    return AgentProductionObservabilityCreate(**payload)


def test_healthy_observation_scores_high():
    service = AgentProductionObservabilitySLOService()
    record = service.create(create_payload())
    assert record.state == AgentProductionObservabilityState.EVIDENCE_READY
    assert record.scores.aggregate_assurance > 0.80
    assert record.dispositions[0].lifecycle_signal == "healthy"
    assert record.risk_flags == []


def test_slo_and_error_budget_alerts_block_approval():
    service = AgentProductionObservabilitySLOService()
    record = service.create(create_payload(observations=[observation(
        availability_slo_attainment=0.80,
        slo_breaches=2,
        error_budget_remaining=0.05,
    )]))
    assert any(flag.startswith("slo-alert:") for flag in record.risk_flags)
    assert any(flag.startswith("error-budget-alert:") for flag in record.risk_flags)
    try:
        service.act(record.workspace_id, record.record_id, "approve", "reviewer", "op-approve")
        assert False, "approval should fail with unresolved findings"
    except ValueError as exc:
        assert "block approval" in str(exc)


def test_critical_incident_can_trigger_risk_brain_hard_block():
    service = AgentProductionObservabilitySLOService()
    record = service.create(create_payload(observations=[observation(
        critical_incidents=1,
        business_criticality=0.95,
    )]))
    assert record.state == AgentProductionObservabilityState.BLOCKED
    assert "risk-brain-hard-block" in record.risk_flags


def test_operation_replay_is_rejected():
    service = AgentProductionObservabilitySLOService()
    record = service.create(create_payload())
    service.act(record.workspace_id, record.record_id, "assess", "reviewer", "same-op")
    try:
        service.act(record.workspace_id, record.record_id, "submit-review", "reviewer", "same-op")
        assert False, "replay should fail"
    except ValueError as exc:
        assert "replay" in str(exc)


def test_workspace_isolation():
    service = AgentProductionObservabilitySLOService()
    record = service.create(create_payload())
    try:
        service.get("other-workspace", record.record_id)
        assert False, "cross-workspace read should fail"
    except KeyError:
        pass


def test_safety_boundary_status():
    status = AgentProductionObservabilitySLOService().status()
    assert status["governance_only"] is True
    assert status["automatic_remediation_enabled"] is False
    assert status["automatic_scaling_enabled"] is False
    assert status["traffic_shift_enabled"] is False
    assert status["automatic_rollback_enabled"] is False
    assert status["agent_execution_enabled"] is False
    assert status["execution_enabled"] is False
