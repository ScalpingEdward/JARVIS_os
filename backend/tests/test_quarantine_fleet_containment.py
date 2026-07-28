import pytest

from app.services.quarantine_fleet_containment import Dependency, QuarantineFleetContainmentService


def quarantine(**overrides):
    value = {
        "record_id": "q1",
        "workspace_id": "ws-1",
        "consumer_id": "consumer-a",
        "status": "quarantined",
        "risk_brain_blocked": False,
    }
    value.update(overrides)
    return value


def deps_with_fallback():
    return [
        Dependency("consumer-b", "ranking", critical=True, fallback_consumer_id="consumer-c", fallback_ready=True),
        Dependency("consumer-d", "monitoring", critical=False),
    ]


def test_clean_containment_requires_two_human_approvals():
    svc = QuarantineFleetContainmentService()
    rec = svc.create(record_id="r1", workspace_id="ws-1", quarantine=quarantine(), dependencies=deps_with_fallback(), source_key="s1")
    assert rec.status == "review-required"
    with pytest.raises(ValueError):
        svc.approve("r1", human_approved=False)
    assert svc.approve("r1", human_approved=True).status == "approved"
    with pytest.raises(ValueError):
        svc.approve_fallback_activation("r1", human_approved=False)
    assert svc.approve_fallback_activation("r1", human_approved=True).status == "fallback-ready"


def test_missing_critical_fallback_blocks():
    svc = QuarantineFleetContainmentService()
    rec = svc.create(
        record_id="r2",
        workspace_id="ws-1",
        quarantine=quarantine(),
        dependencies=[Dependency("consumer-b", "dispatch", critical=True)],
        source_key="s2",
    )
    assert rec.status == "blocked"
    assert rec.critical_gap_count == 1
    assert "critical-dependency-without-fallback" in rec.findings


def test_non_quarantined_admission_blocks():
    svc = QuarantineFleetContainmentService()
    rec = svc.create(record_id="r3", workspace_id="ws-1", quarantine=quarantine(status="readopted"), dependencies=deps_with_fallback(), source_key="s3")
    assert rec.status == "blocked"
    assert "consumer-not-quarantined" in rec.findings


def test_risk_brain_block_propagates():
    svc = QuarantineFleetContainmentService()
    rec = svc.create(record_id="r4", workspace_id="ws-1", quarantine=quarantine(risk_brain_blocked=True), dependencies=deps_with_fallback(), source_key="s4")
    assert rec.risk_brain_blocked
    assert rec.status == "blocked"


def test_replay_protection_and_workspace_isolation():
    svc = QuarantineFleetContainmentService()
    svc.create(record_id="r5", workspace_id="ws-1", quarantine=quarantine(), dependencies=deps_with_fallback(), source_key="same")
    with pytest.raises(ValueError):
        svc.create(record_id="r6", workspace_id="ws-1", quarantine=quarantine(), dependencies=deps_with_fallback(), source_key="same")
    rec = svc.create(record_id="r7", workspace_id="ws-2", quarantine=quarantine(), dependencies=deps_with_fallback(), source_key="same")
    assert rec.status == "blocked"
    assert "workspace-mismatch" in rec.findings


def test_impact_metadata_is_deterministic_and_bounded():
    svc = QuarantineFleetContainmentService()
    rec = svc.create(record_id="r8", workspace_id="ws-1", quarantine=quarantine(), dependencies=deps_with_fallback(), source_key="s8")
    assert rec.affected_consumers == ["consumer-b", "consumer-d"]
    assert 0.0 <= rec.blast_radius_score <= 1.0
    assert 0.0 <= rec.residual_risk <= 1.0
    assert rec.containment_digest
