import pytest

from app.schemas.operational_resilience_incident import OperationalResilienceCreate, ResilienceObservation
from app.services.operational_resilience_incident import OperationalResilienceIncidentService


def _payload(source_key: str = "ops-1", critical: bool = False) -> OperationalResilienceCreate:
    observation = ResilienceObservation(
        service_id="execution-gateway",
        criticality=0.95 if critical else 0.80,
        availability_score=0.99 if not critical else 0.40,
        recovery_readiness=0.90 if not critical else 0.30,
        continuity_readiness=0.90 if not critical else 0.40,
        dependency_resilience=0.85 if not critical else 0.45,
        capacity_headroom=0.60 if not critical else 0.15,
        cyber_resilience=0.90 if not critical else 0.50,
        runbook_coverage=0.90 if not critical else 0.40,
        recovery_test_coverage=0.85 if not critical else 0.35,
        incident_count_30d=1 if not critical else 12,
        open_sev1_incidents=0 if not critical else 1,
        rto_breach_risk=0.05 if not critical else 0.80,
        rpo_breach_risk=0.05 if not critical else 0.70,
        confidence=0.95,
        freshness=0.95,
    )
    return OperationalResilienceCreate(
        workspace_id="ws-a",
        source_key=source_key,
        requested_by="tester",
        observations=[observation],
    )


def test_status_enforces_advisory_only_boundary():
    service = OperationalResilienceIncidentService()
    status = service.status()
    assert status["governance_only"] is True
    assert status["infrastructure_mutation_enabled"] is False
    assert status["failover_execution_enabled"] is False
    assert status["service_restart_enabled"] is False
    assert status["execution_enabled"] is False
    assert status["human_approval_required"] is True


def test_assessment_scores_resilience_and_clean_record_can_be_approved():
    service = OperationalResilienceIncidentService()
    record = service.create(_payload())
    assert record.scores.aggregate_resilience > 0.70
    assert record.risk_flags == []
    reviewed = service.act("ws-a", record.record_id, "submit-review", "reviewer", "op-1")
    assert reviewed.state.value == "review-required"
    approved = service.act("ws-a", record.record_id, "approve", "human", "op-2")
    assert approved.state.value == "approved"
    activated = service.act("ws-a", record.record_id, "activate", "human", "op-3")
    assert activated.state.value == "active"


def test_critical_incident_triggers_risk_brain_hard_block():
    service = OperationalResilienceIncidentService()
    record = service.create(_payload("critical", critical=True))
    assert record.state.value == "blocked"
    assert "risk-brain-hard-block" in record.risk_flags
    assert "incident-alert:execution-gateway" in record.risk_flags
    with pytest.raises(ValueError, match="flags block approval"):
        service.act("ws-a", record.record_id, "approve", "human", "op-4")


def test_replay_and_workspace_isolation():
    service = OperationalResilienceIncidentService()
    record = service.create(_payload("isolated"))
    service.act("ws-a", record.record_id, "assess", "reviewer", "receipt-1")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "monitor", "reviewer", "receipt-1")
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = OperationalResilienceIncidentService()
    service.create(_payload("dup"))
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(_payload("dup"))
