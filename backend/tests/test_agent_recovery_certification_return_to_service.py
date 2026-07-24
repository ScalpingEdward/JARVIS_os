import pytest

from app.schemas.agent_recovery_certification_return_to_service import RecoveryCertificationCreate
from app.services.agent_recovery_certification_return_to_service import AgentRecoveryCertificationReturnToServiceService


def payload(**overrides):
    observation = {
        "agent_id": "phoenix-agent", "agent_version": "21.106", "recovery_id": "recovery-001",
        "service_health_score": 0.99, "state_integrity_score": 0.99, "data_integrity_score": 0.99,
        "dependency_health_score": 0.98, "observability_score": 0.98, "error_budget_readiness": 0.95,
        "capacity_headroom": 0.60, "business_validation_score": 0.98, "rollback_readiness": 0.98,
        "human_signoff_coverage": 1.0, "confidence": 1.0, "freshness": 1.0, "criticality": 0.70,
    }
    observation.update(overrides)
    return RecoveryCertificationCreate(
        workspace_id="ws-a", source_key="recovery-source", requested_by="operator", observations=[observation]
    )


def test_status_is_governance_only():
    status = AgentRecoveryCertificationReturnToServiceService().status()
    assert status["version"] == "21.106"
    assert status["return_to_service_execution_enabled"] is False
    assert status["traffic_shift_enabled"] is False
    assert status["runtime_restart_enabled"] is False
    assert status["automatic_recovery_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_clean_recovery_can_be_approved_and_certified():
    service = AgentRecoveryCertificationReturnToServiceService()
    record = service.create(payload())
    assert not record.risk_flags
    record = service.act("ws-a", record.record_id, "assess", "reviewer", "op-1")
    record = service.act("ws-a", record.record_id, "submit-review", "reviewer", "op-2")
    record = service.act("ws-a", record.record_id, "approve", "owner", "op-3")
    record = service.act("ws-a", record.record_id, "certify", "owner", "op-4")
    assert record.state.value == "certified"


def test_integrity_findings_block_approval():
    service = AgentRecoveryCertificationReturnToServiceService()
    record = service.create(payload(state_integrity_score=0.40, integrity_failures=1))
    assert any(flag.startswith("integrity-alert") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "owner", "op-a")


def test_critical_failed_recovery_hard_blocks():
    service = AgentRecoveryCertificationReturnToServiceService()
    record = service.create(payload(
        criticality=0.98, service_health_score=0.40, state_integrity_score=0.30,
        data_integrity_score=0.30, unresolved_recovery_findings=2,
        integrity_failures=1, business_validation_failures=1,
    ))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_operation_replay_rejected():
    service = AgentRecoveryCertificationReturnToServiceService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "assess", "reviewer", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "submit-review", "reviewer", "same-op")


def test_workspace_isolation_and_duplicate_source_protection():
    service = AgentRecoveryCertificationReturnToServiceService()
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
