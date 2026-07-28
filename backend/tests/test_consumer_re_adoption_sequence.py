import pytest

from app.services.consumer_re_adoption_sequence import ConsumerReAdoptionSequenceService


def plan(**overrides):
    value = {
        "record_id": "plan-1",
        "workspace_id": "ws-1",
        "status": "remediation-ready",
        "human_approved": True,
        "risk_brain_blocked": False,
        "baseline_id": "baseline-1",
        "baseline_version": 3,
        "baseline_digest": "digest-3",
        "affected_consumers": ["adapter-selection", "worker-selection"],
        "healthy_consumers": ["dispatch-planning"],
    }
    value.update(overrides)
    return value


def test_sequence_requires_authorization_and_per_step_approval():
    svc = ConsumerReAdoptionSequenceService()
    rec = svc.create(record_id="r1", workspace_id="ws-1", remediation_plan=plan(), source_key="s1")
    assert rec.status == "review-required"
    with pytest.raises(ValueError):
        svc.authorize("r1", human_approved=False)
    assert svc.authorize("r1", human_approved=True).status == "authorized"
    assert svc.approve_next_step("r1", human_approved=True).status == "staged"
    assert svc.approve_next_step("r1", human_approved=True).status == "recovery-ready"


def test_invalid_admission_blocks():
    svc = ConsumerReAdoptionSequenceService()
    rec = svc.create(record_id="r2", workspace_id="ws-1", remediation_plan=plan(status="review-required"), source_key="s2")
    assert rec.status == "blocked"
    assert "remediation-not-ready" in rec.findings


def test_risk_brain_block_propagates():
    svc = ConsumerReAdoptionSequenceService()
    rec = svc.create(record_id="r3", workspace_id="ws-1", remediation_plan=plan(risk_brain_blocked=True), source_key="s3")
    assert rec.status == "blocked"
    assert rec.risk_brain_blocked


def test_missing_baseline_binding_blocks():
    svc = ConsumerReAdoptionSequenceService()
    rec = svc.create(record_id="r4", workspace_id="ws-1", remediation_plan=plan(baseline_digest=""), source_key="s4")
    assert rec.status == "blocked"
    assert "baseline-binding-missing" in rec.findings


def test_healthy_and_affected_overlap_blocks():
    svc = ConsumerReAdoptionSequenceService()
    rec = svc.create(record_id="r5", workspace_id="ws-1", remediation_plan=plan(healthy_consumers=["adapter-selection"]), source_key="s5")
    assert rec.status == "blocked"
    assert "consumer-set-overlap" in rec.findings


def test_replay_and_workspace_isolation():
    svc = ConsumerReAdoptionSequenceService()
    svc.create(record_id="r6", workspace_id="ws-1", remediation_plan=plan(), source_key="same")
    with pytest.raises(ValueError):
        svc.create(record_id="r7", workspace_id="ws-1", remediation_plan=plan(), source_key="same")
    rec = svc.create(record_id="r8", workspace_id="ws-2", remediation_plan=plan(), source_key="same")
    assert rec.status == "blocked"
    assert "workspace-mismatch" in rec.findings


def test_no_affected_consumers_blocks():
    svc = ConsumerReAdoptionSequenceService()
    rec = svc.create(record_id="r9", workspace_id="ws-1", remediation_plan=plan(affected_consumers=[]), source_key="s9")
    assert rec.status == "blocked"
    assert "no-affected-consumers" in rec.findings
