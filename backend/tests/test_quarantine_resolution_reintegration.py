import pytest
from app.services.quarantine_resolution_reintegration import QuarantineResolutionReintegrationService


def readiness(**overrides):
    value = {
        "record_id": "ready-1", "workspace_id": "ws-1", "status": "resolution-ready",
        "human_approved": True, "risk_brain_blocked": False, "consumer_id": "consumer-a",
        "baseline_id": "base-1", "baseline_version": 7, "baseline_digest": "digest-7",
    }
    value.update(overrides)
    return value


def quarantine(**overrides):
    value = {
        "record_id": "q-1", "workspace_id": "ws-1", "status": "quarantined",
        "consumer_id": "consumer-a", "baseline_id": "base-1", "baseline_version": 7,
        "baseline_digest": "digest-7", "risk_brain_blocked": False,
    }
    value.update(overrides)
    return value


def test_clean_reintegration_requires_approval_and_staged_human_advancement():
    svc = QuarantineResolutionReintegrationService()
    rec = svc.create(record_id="r1", workspace_id="ws-1", resolution_readiness=readiness(), quarantine_record=quarantine(), source_key="s1", max_stage=2)
    assert rec.status == "review-required"
    with pytest.raises(ValueError):
        svc.approve("r1", human_approved=False)
    assert svc.approve("r1", human_approved=True).status == "authorized"
    with pytest.raises(ValueError):
        svc.advance_stage("r1", human_approved=False)
    assert svc.advance_stage("r1", human_approved=True).status == "staged"
    assert svc.advance_stage("r1", human_approved=True).status == "reintegrated"


def test_baseline_binding_mismatch_blocks():
    svc = QuarantineResolutionReintegrationService()
    rec = svc.create(record_id="r2", workspace_id="ws-1", resolution_readiness=readiness(baseline_version=8), quarantine_record=quarantine(), source_key="s2")
    assert rec.status == "blocked"
    assert "baseline_version-binding-mismatch" in rec.findings


def test_consumer_binding_mismatch_blocks():
    svc = QuarantineResolutionReintegrationService()
    rec = svc.create(record_id="r3", workspace_id="ws-1", resolution_readiness=readiness(consumer_id="consumer-b"), quarantine_record=quarantine(), source_key="s3")
    assert rec.status == "blocked"
    assert "consumer-binding-mismatch" in rec.findings


def test_risk_brain_block_propagates():
    svc = QuarantineResolutionReintegrationService()
    rec = svc.create(record_id="r4", workspace_id="ws-1", resolution_readiness=readiness(risk_brain_blocked=True), quarantine_record=quarantine(), source_key="s4")
    assert rec.risk_brain_blocked
    assert rec.status == "blocked"


def test_invalid_admission_and_workspace_fail_closed():
    svc = QuarantineResolutionReintegrationService()
    rec = svc.create(record_id="r5", workspace_id="ws-2", resolution_readiness=readiness(status="degraded"), quarantine_record=quarantine(), source_key="s5")
    assert rec.status == "blocked"
    assert "readiness-not-approved" in rec.findings
    assert "readiness-workspace-mismatch" in rec.findings


def test_replay_protection():
    svc = QuarantineResolutionReintegrationService()
    svc.create(record_id="r6", workspace_id="ws-1", resolution_readiness=readiness(), quarantine_record=quarantine(), source_key="same")
    with pytest.raises(ValueError):
        svc.create(record_id="r7", workspace_id="ws-1", resolution_readiness=readiness(), quarantine_record=quarantine(), source_key="same")
