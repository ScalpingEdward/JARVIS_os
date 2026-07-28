import pytest
from app.services.baseline_consumer_quarantine import BaselineConsumerQuarantineService


def drift(**overrides):
    value = {
        "receipt_id": "r1", "workspace_id": "ws-1", "consumer_id": "dispatch-planning",
        "status": "drift-reviewed", "risk_brain_blocked": False,
        "expected_baseline_id": "b1", "expected_baseline_version": 3,
        "expected_baseline_digest": "digest-3",
    }
    value.update(overrides)
    return value


def adopted(**overrides):
    value = {
        "receipt_id": "r2", "workspace_id": "ws-1", "consumer_id": "dispatch-planning",
        "status": "adopted", "risk_brain_blocked": False,
        "baseline_id": "b1", "baseline_version": 3, "baseline_digest": "digest-3",
    }
    value.update(overrides)
    return value


def test_reviewed_drift_can_be_quarantined_then_readopted():
    svc = BaselineConsumerQuarantineService()
    rec = svc.create_from_drift(record_id="q1", workspace_id="ws-1", drift_receipt=drift(), source_key="s1")
    assert rec.status == "review-required"
    with pytest.raises(ValueError):
        svc.quarantine("q1", human_approved=False)
    assert svc.quarantine("q1", human_approved=True).status == "quarantined"
    assert svc.submit_readoption("q1", receipt=adopted()).status == "readoption-review-required"
    assert svc.approve_readoption("q1", human_approved=True).status == "readopted"


def test_unreviewed_drift_blocks():
    svc = BaselineConsumerQuarantineService()
    rec = svc.create_from_drift(record_id="q2", workspace_id="ws-1", drift_receipt=drift(status="drift-detected"), source_key="s2")
    assert rec.status == "blocked"


def test_wrong_baseline_keeps_consumer_quarantined():
    svc = BaselineConsumerQuarantineService()
    svc.create_from_drift(record_id="q3", workspace_id="ws-1", drift_receipt=drift(), source_key="s3")
    svc.quarantine("q3", human_approved=True)
    rec = svc.submit_readoption("q3", receipt=adopted(baseline_version=4))
    assert rec.status == "quarantined"
    assert "baseline-version-mismatch" in rec.findings


def test_consumer_and_digest_mismatch_fail_closed():
    svc = BaselineConsumerQuarantineService()
    svc.create_from_drift(record_id="q4", workspace_id="ws-1", drift_receipt=drift(), source_key="s4")
    svc.quarantine("q4", human_approved=True)
    rec = svc.submit_readoption("q4", receipt=adopted(consumer_id="worker-selection", baseline_digest="wrong"))
    assert "consumer-mismatch" in rec.findings
    assert "baseline-digest-mismatch" in rec.findings


def test_risk_brain_block_propagates():
    svc = BaselineConsumerQuarantineService()
    rec = svc.create_from_drift(record_id="q5", workspace_id="ws-1", drift_receipt=drift(risk_brain_blocked=True), source_key="s5")
    assert rec.status == "blocked"
    assert rec.risk_brain_blocked


def test_replay_and_workspace_isolation():
    svc = BaselineConsumerQuarantineService()
    svc.create_from_drift(record_id="q6", workspace_id="ws-1", drift_receipt=drift(), source_key="same")
    with pytest.raises(ValueError):
        svc.create_from_drift(record_id="q7", workspace_id="ws-1", drift_receipt=drift(), source_key="same")
    rec = svc.create_from_drift(record_id="q8", workspace_id="ws-2", drift_receipt=drift(), source_key="same")
    assert rec.status == "blocked"
    assert "workspace-mismatch" in rec.findings
