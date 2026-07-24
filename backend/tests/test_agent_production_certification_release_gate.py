import pytest

from app.schemas.agent_production_certification_release_gate import AgentProductionCertificationCreate
from app.services.agent_production_certification_release_gate import (
    AgentProductionCertificationReleaseGateService,
)


def _payload(**overrides):
    observation = {
        "agent_id": "execution-agent-1",
        "agent_version": "1.0.0",
        "target_environment": "production-eu",
        "environment_parity_score": 0.98,
        "artifact_integrity_score": 1.0,
        "configuration_integrity_score": 0.98,
        "dependency_lock_score": 0.98,
        "security_signoff_coverage": 1.0,
        "risk_signoff_coverage": 1.0,
        "operations_signoff_coverage": 1.0,
        "change_window_readiness": 0.95,
        "release_gate_coverage": 1.0,
        "observability_baseline_score": 0.95,
        "rollback_recovery_readiness": 0.95,
        "break_glass_readiness": 0.95,
        "runbook_readiness": 0.95,
        "confidence": 0.95,
        "freshness": 1.0,
        "unresolved_blocking_findings": 0,
        "missing_required_signoffs": 0,
        "environment_drift_events": 0,
        "failed_release_gate_checks": 0,
        "rollback_recovery_failures": 0,
        "business_criticality": 0.75,
    }
    observation.update(overrides.pop("observation", {}))
    payload = {
        "workspace_id": "workspace-a",
        "source_key": "prod-cert-001",
        "requested_by": "release-owner",
        "observations": [observation],
    }
    payload.update(overrides)
    return AgentProductionCertificationCreate(**payload)


def test_status_is_advisory_only():
    service = AgentProductionCertificationReleaseGateService()
    status = service.status()
    assert status["version"] == "21.96"
    assert status["deployment_execution_enabled"] is False
    assert status["release_gate_mutation_enabled"] is False
    assert status["traffic_shift_enabled"] is False
    assert status["automatic_rollback_enabled"] is False
    assert status["agent_execution_enabled"] is False
    assert status["execution_enabled"] is False
    assert status["risk_brain_authoritative"] is True


def test_healthy_candidate_can_be_approved_and_certified():
    service = AgentProductionCertificationReleaseGateService()
    record = service.create(_payload())
    assert record.risk_flags == []
    assessed = service.act("workspace-a", record.record_id, "assess", "owner", "op-1")
    assert assessed.state.value == "assessed"
    reviewed = service.act("workspace-a", record.record_id, "submit-review", "owner", "op-2")
    assert reviewed.state.value == "review-required"
    approved = service.act("workspace-a", record.record_id, "approve", "human-approver", "op-3")
    assert approved.approved_by == "human-approver"
    active = service.act("workspace-a", record.record_id, "activate", "human-approver", "op-4")
    assert active.state.value == "active"
    certified = service.act("workspace-a", record.record_id, "certify", "human-approver", "op-5")
    assert certified.state.value == "certified"


def test_environment_drift_blocks_approval():
    service = AgentProductionCertificationReleaseGateService()
    record = service.create(
        _payload(observation={"environment_parity_score": 0.70, "environment_drift_events": 1})
    )
    assert any(flag.startswith("environment-alert:") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("workspace-a", record.record_id, "approve", "owner", "op-a")


def test_missing_signoff_is_flagged():
    service = AgentProductionCertificationReleaseGateService()
    record = service.create(
        _payload(observation={"security_signoff_coverage": 0.50, "missing_required_signoffs": 1})
    )
    assert any(flag.startswith("signoff-alert:") for flag in record.risk_flags)
    assert record.dispositions[0].lifecycle_signal == "signoff-alert"


def test_failed_release_gate_is_flagged():
    service = AgentProductionCertificationReleaseGateService()
    record = service.create(_payload(observation={"failed_release_gate_checks": 1}))
    assert any(flag.startswith("release-gate-alert:") for flag in record.risk_flags)


def test_critical_recovery_failure_hard_blocks():
    service = AgentProductionCertificationReleaseGateService()
    record = service.create(
        _payload(
            observation={
                "business_criticality": 0.95,
                "rollback_recovery_failures": 1,
                "rollback_recovery_readiness": 0.40,
            }
        )
    )
    assert record.state.value == "blocked"
    assert "risk-brain-hard-block" in record.risk_flags


def test_operation_replay_is_rejected():
    service = AgentProductionCertificationReleaseGateService()
    record = service.create(_payload())
    service.act("workspace-a", record.record_id, "assess", "owner", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("workspace-a", record.record_id, "monitor", "owner", "same-op")


def test_workspace_isolation():
    service = AgentProductionCertificationReleaseGateService()
    record = service.create(_payload())
    with pytest.raises(KeyError):
        service.get("workspace-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = AgentProductionCertificationReleaseGateService()
    service.create(_payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(_payload())


def test_duplicate_agent_environment_pair_is_rejected():
    base = _payload().model_dump()
    base["source_key"] = "prod-cert-dup"
    base["observations"] = [base["observations"][0], base["observations"][0]]
    with pytest.raises(ValueError, match="duplicate agent/environment observation"):
        AgentProductionCertificationCreate(**base)
