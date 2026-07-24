import pytest

from app.schemas.agent_production_incident_response import AgentProductionIncidentCreate
from app.services.agent_production_incident_response import AgentProductionIncidentResponseService


def payload(**overrides):
    observation = {
        "agent_id": "phoenix-agent", "agent_version": "21.98", "incident_id": "inc-001",
        "severity": 0.20, "detection_quality": 0.98, "triage_readiness": 0.98,
        "containment_readiness": 0.98, "recovery_readiness": 0.98, "rollback_readiness": 0.98,
        "human_command_coverage": 1.0, "stakeholder_communication_readiness": 0.98,
        "evidence_preservation_score": 0.98, "postmortem_readiness": 0.98,
        "lessons_learned_traceability": 0.98, "confidence": 1.0, "freshness": 1.0,
        "business_criticality": 0.70,
    }
    observation.update(overrides)
    return AgentProductionIncidentCreate(
        workspace_id="ws-a", source_key="incident-source", requested_by="operator", observations=[observation]
    )


def test_status_is_advisory_only():
    status = AgentProductionIncidentResponseService().status()
    assert status["version"] == "21.98"
    assert status["automatic_containment_enabled"] is False
    assert status["automatic_recovery_enabled"] is False
    assert status["automatic_rollback_enabled"] is False
    assert status["agent_execution_enabled"] is False
    assert status["execution_enabled"] is False


def test_healthy_incident_can_be_approved_after_review():
    service = AgentProductionIncidentResponseService()
    record = service.create(payload())
    assert not record.risk_flags
    record = service.act("ws-a", record.record_id, "assess", "reviewer", "op-1")
    record = service.act("ws-a", record.record_id, "submit-review", "reviewer", "op-2")
    record = service.act("ws-a", record.record_id, "approve", "human-owner", "op-3")
    assert record.approved_by == "human-owner"


def test_findings_block_approval():
    service = AgentProductionIncidentResponseService()
    record = service.create(payload(containment_readiness=0.40, containment_failures=1))
    assert any(flag.startswith("containment-alert") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "human-owner", "op-a")


def test_critical_incident_triggers_risk_brain_hard_block():
    service = AgentProductionIncidentResponseService()
    record = service.create(payload(
        severity=0.95, business_criticality=0.98, unresolved_critical_impacts=1,
        containment_failures=1, recovery_failures=1,
    ))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_operation_replay_is_rejected():
    service = AgentProductionIncidentResponseService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "assess", "reviewer", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "submit-review", "reviewer", "same-op")


def test_workspace_isolation():
    service = AgentProductionIncidentResponseService()
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = AgentProductionIncidentResponseService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
