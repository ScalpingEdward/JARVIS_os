import pytest

from app.schemas.agent_disaster_recovery_service_continuity import DisasterRecoveryCreate
from app.services.agent_disaster_recovery_service_continuity import AgentDisasterRecoveryServiceContinuityService


def payload(**overrides):
    observation = {
        "agent_id": "phoenix-agent", "agent_version": "21.104", "service_id": "core-service",
        "rto_readiness": 0.98, "rpo_readiness": 0.98, "backup_integrity": 0.99,
        "restore_readiness": 0.98, "regional_redundancy": 0.95,
        "dependency_recovery_readiness": 0.95, "state_reconstruction_readiness": 0.95,
        "communication_readiness": 0.95, "runbook_coverage": 0.98,
        "recovery_test_coverage": 0.98, "confidence": 1.0, "freshness": 1.0,
        "criticality": 0.70,
    }
    observation.update(overrides)
    return DisasterRecoveryCreate(
        workspace_id="ws-a", source_key="dr-source", requested_by="operator", observations=[observation]
    )


def test_status_disables_execution():
    status = AgentDisasterRecoveryServiceContinuityService().status()
    assert status["version"] == "21.104"
    assert status["automatic_restore_enabled"] is False
    assert status["automatic_failover_enabled"] is False
    assert status["automatic_recovery_enabled"] is False
    assert status["agent_execution_enabled"] is False
    assert status["execution_enabled"] is False


def test_healthy_record_can_be_approved():
    service = AgentDisasterRecoveryServiceContinuityService()
    record = service.create(payload())
    assert not record.risk_flags
    record = service.act("ws-a", record.record_id, "assess", "reviewer", "op-1")
    record = service.act("ws-a", record.record_id, "submit-review", "reviewer", "op-2")
    record = service.act("ws-a", record.record_id, "approve", "owner", "op-3")
    assert record.approved_by == "owner"


def test_backup_findings_block_approval():
    service = AgentDisasterRecoveryServiceContinuityService()
    record = service.create(payload(backup_integrity=0.40, stale_backup_events=1))
    assert any(flag.startswith("backup-alert") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "owner", "op-a")


def test_critical_recovery_failure_hard_blocks():
    service = AgentDisasterRecoveryServiceContinuityService()
    record = service.create(payload(
        criticality=0.98, restore_readiness=0.20, failed_restore_tests=1,
        failed_recovery_tests=1, continuity_gaps=2,
    ))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_operation_replay_rejected():
    service = AgentDisasterRecoveryServiceContinuityService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "assess", "reviewer", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "submit-review", "reviewer", "same-op")


def test_workspace_isolation():
    service = AgentDisasterRecoveryServiceContinuityService()
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_rejected():
    service = AgentDisasterRecoveryServiceContinuityService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
