import pytest

from app.services.reliability_feedback_impact_preview import ReliabilityFeedbackImpactPreviewService


def feedback(**overrides):
    value = {
        "workspace_id": "ws-1",
        "status": "approved-feedback",
        "human_approved": True,
        "baseline_id": "baseline-a",
        "baseline_version": 7,
        "baseline_digest": "digest-a",
        "baseline_before": 0.80,
        "proposed_baseline": 0.84,
        "risk_brain_blocked": False,
    }
    value.update(overrides)
    return value


def test_clean_preview_requires_human_approval():
    svc = ReliabilityFeedbackImpactPreviewService()
    rec = svc.create(record_id="r1", workspace_id="ws-1", approved_feedback=feedback(), source_key="s1")
    assert rec.status == "review-required"
    with pytest.raises(ValueError):
        svc.approve("r1", human_approved=False)
    assert svc.approve("r1", human_approved=True).status == "approved-preview"


def test_large_change_blocks():
    svc = ReliabilityFeedbackImpactPreviewService()
    rec = svc.create(record_id="r2", workspace_id="ws-1", approved_feedback=feedback(proposed_baseline=1.0), source_key="s2")
    assert rec.status == "blocked"
    assert rec.findings


def test_invalid_admission_blocks():
    svc = ReliabilityFeedbackImpactPreviewService()
    rec = svc.create(record_id="r3", workspace_id="ws-1", approved_feedback=feedback(status="review-required"), source_key="s3")
    assert rec.status == "blocked"
    assert "feedback-not-approved" in rec.findings


def test_missing_baseline_binding_blocks():
    svc = ReliabilityFeedbackImpactPreviewService()
    rec = svc.create(record_id="r4", workspace_id="ws-1", approved_feedback=feedback(baseline_digest=""), source_key="s4")
    assert rec.status == "blocked"
    assert "baseline-binding-missing" in rec.findings


def test_risk_brain_block_propagates():
    svc = ReliabilityFeedbackImpactPreviewService()
    rec = svc.create(record_id="r5", workspace_id="ws-1", approved_feedback=feedback(risk_brain_blocked=True), source_key="s5")
    assert rec.status == "blocked"
    assert rec.risk_brain_blocked


def test_replay_and_workspace_isolation():
    svc = ReliabilityFeedbackImpactPreviewService()
    svc.create(record_id="r6", workspace_id="ws-1", approved_feedback=feedback(), source_key="same")
    with pytest.raises(ValueError):
        svc.create(record_id="r7", workspace_id="ws-1", approved_feedback=feedback(), source_key="same")
    rec = svc.create(record_id="r8", workspace_id="ws-2", approved_feedback=feedback(), source_key="same")
    assert rec.status == "blocked"
    assert "workspace-mismatch" in rec.findings
