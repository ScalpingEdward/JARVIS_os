import pytest
from app.services.cross_consumer_drift_remediation import CrossConsumerDriftRemediationService


def evidence(**overrides):
    value = {
        "workspace_id": "ws-1",
        "status": "inconsistent",
        "risk_brain_blocked": False,
        "baseline_id": "rb-1",
        "baseline_version": 3,
        "baseline_digest": "digest-3",
        "eligible_consumers": ["adapter-selection", "worker-selection", "dispatch-planning"],
        "receipts": [
            {"consumer": "adapter-selection", "status": "adopted", "baseline_id": "rb-1", "baseline_version": 3, "baseline_digest": "digest-3"},
            {"consumer": "worker-selection", "status": "adopted", "baseline_id": "rb-1", "baseline_version": 2, "baseline_digest": "digest-2"},
            {"consumer": "dispatch-planning", "status": "adopted", "baseline_id": "rb-1", "baseline_version": 3, "baseline_digest": "digest-3"},
        ],
    }
    value.update(overrides)
    return value


def test_drift_plan_requires_human_approval():
    svc = CrossConsumerDriftRemediationService()
    rec = svc.create(record_id="r1", workspace_id="ws-1", inconsistent_evidence=evidence(), source_key="s1")
    assert rec.status == "review-required"
    assert rec.affected_consumers == ["worker-selection"]
    with pytest.raises(ValueError):
        svc.approve("r1", human_approved=False)
    assert svc.approve("r1", human_approved=True).status == "remediation-ready"


def test_large_blast_radius_fails_closed():
    svc = CrossConsumerDriftRemediationService()
    ev = evidence(receipts=[])
    rec = svc.create(record_id="r2", workspace_id="ws-1", inconsistent_evidence=ev, source_key="s2", max_blast_radius=0.50)
    assert rec.status == "blocked"
    assert "blast-radius-above-limit" in rec.findings


def test_invalid_admission_and_workspace_mismatch_block():
    svc = CrossConsumerDriftRemediationService()
    rec = svc.create(record_id="r3", workspace_id="ws-2", inconsistent_evidence=evidence(status="consistent"), source_key="s3")
    assert rec.status == "blocked"
    assert "workspace-mismatch" in rec.findings
    assert "admission-state-not-inconsistent" in rec.findings


def test_risk_brain_block_propagates():
    svc = CrossConsumerDriftRemediationService()
    rec = svc.create(record_id="r4", workspace_id="ws-1", inconsistent_evidence=evidence(risk_brain_blocked=True), source_key="s4")
    assert rec.risk_brain_blocked
    assert rec.status == "blocked"


def test_missing_baseline_binding_blocks():
    svc = CrossConsumerDriftRemediationService()
    rec = svc.create(record_id="r5", workspace_id="ws-1", inconsistent_evidence=evidence(baseline_digest=""), source_key="s5")
    assert rec.status == "blocked"
    assert "baseline-binding-missing" in rec.findings


def test_replay_and_workspace_scoping():
    svc = CrossConsumerDriftRemediationService()
    svc.create(record_id="r6", workspace_id="ws-1", inconsistent_evidence=evidence(), source_key="same")
    with pytest.raises(ValueError):
        svc.create(record_id="r7", workspace_id="ws-1", inconsistent_evidence=evidence(), source_key="same")
    rec = svc.create(record_id="r8", workspace_id="ws-2", inconsistent_evidence=evidence(workspace_id="ws-2"), source_key="same")
    assert rec.workspace_id == "ws-2"
