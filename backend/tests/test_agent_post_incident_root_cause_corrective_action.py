import pytest

from app.schemas.agent_post_incident_root_cause_corrective_action import AgentPostIncidentRcaCreate
from app.services.agent_post_incident_root_cause_corrective_action import AgentPostIncidentRootCauseCorrectiveActionService


def payload(**overrides):
    observation = {
        "agent_id": "phoenix-agent", "agent_version": "21.99", "incident_id": "inc-001",
        "root_cause_confidence": 0.98, "evidence_completeness": 0.98, "causal_chain_coverage": 0.98,
        "contributing_factor_coverage": 0.98, "corrective_action_quality": 0.98,
        "preventive_action_quality": 0.98, "owner_accountability": 1.0, "due_date_readiness": 0.98,
        "verification_plan_quality": 0.98, "recurrence_prevention_score": 0.98,
        "cross_agent_impact_review": 0.98, "confidence": 1.0, "freshness": 1.0,
        "business_criticality": 0.70,
    }
    observation.update(overrides)
    return AgentPostIncidentRcaCreate(
        workspace_id="ws-a", source_key="rca-source", requested_by="operator", observations=[observation]
    )


def test_status_is_governance_only():
    status = AgentPostIncidentRootCauseCorrectiveActionService().status()
    assert status["version"] == "21.99"
    assert status["automatic_remediation_enabled"] is False
    assert status["automatic_change_enabled"] is False
    assert status["automatic_deployment_enabled"] is False
    assert status["execution_enabled"] is False


def test_clean_record_can_be_approved():
    service = AgentPostIncidentRootCauseCorrectiveActionService()
    record = service.create(payload())
    assert not record.risk_flags
    record = service.act("ws-a", record.record_id, "approve", "human-owner", "op-1")
    assert record.approved_by == "human-owner"


def test_unresolved_root_cause_blocks_approval():
    service = AgentPostIncidentRootCauseCorrectiveActionService()
    record = service.create(payload(root_cause_confidence=0.40, unresolved_root_causes=1))
    assert any(flag.startswith("root-cause-alert") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "human-owner", "op-a")


def test_repeat_critical_incident_triggers_hard_block():
    service = AgentPostIncidentRootCauseCorrectiveActionService()
    record = service.create(payload(
        business_criticality=0.98, unresolved_root_causes=1,
        failed_verification_checks=1, repeat_incident_count=2,
    ))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_operation_replay_is_rejected():
    service = AgentPostIncidentRootCauseCorrectiveActionService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "assess", "reviewer", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "submit-review", "reviewer", "same-op")


def test_workspace_isolation():
    service = AgentPostIncidentRootCauseCorrectiveActionService()
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = AgentPostIncidentRootCauseCorrectiveActionService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
