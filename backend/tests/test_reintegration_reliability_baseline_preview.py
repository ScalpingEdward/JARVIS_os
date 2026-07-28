import pytest
from app.services.reintegration_reliability_baseline_preview import ReintegrationReliabilityBaselinePreviewService


def episode(**overrides):
    value = {
        "workspace_id": "ws-1",
        "status": "closed",
        "human_approved": True,
        "risk_brain_blocked": False,
        "consumer_id": "consumer-a",
        "baseline_id": "baseline-a",
        "baseline_version": 3,
        "baseline_digest": "digest-a",
        "proposed_reliability": 0.84,
        "aggregate_confidence": 0.93,
        "residual_risk": 0.08,
    }
    value.update(overrides)
    return value


def test_clean_preview_requires_human_approval():
    svc = ReintegrationReliabilityBaselinePreviewService()
    rec = svc.create(record_id="r1", workspace_id="ws-1", closed_episode=episode(), current_reliability=0.80, source_key="s1")
    assert rec.status == "review-required"
    assert rec.score_delta == 0.04
    with pytest.raises(ValueError):
        svc.approve("r1", human_approved=False)
    assert svc.approve("r1", human_approved=True).status == "approved-preview"


def test_large_delta_blocks():
    svc = ReintegrationReliabilityBaselinePreviewService()
    rec = svc.create(record_id="r2", workspace_id="ws-1", closed_episode=episode(proposed_reliability=0.98), current_reliability=0.70, source_key="s2")
    assert rec.status == "blocked"
    assert "score-delta-above-limit" in rec.findings


def test_invalid_admission_blocks():
    svc = ReintegrationReliabilityBaselinePreviewService()
    rec = svc.create(record_id="r3", workspace_id="ws-1", closed_episode=episode(status="review-required"), current_reliability=0.8, source_key="s3")
    assert rec.status == "blocked"
    assert "episode-not-closed" in rec.findings


def test_missing_binding_blocks():
    svc = ReintegrationReliabilityBaselinePreviewService()
    rec = svc.create(record_id="r4", workspace_id="ws-1", closed_episode=episode(baseline_digest=""), current_reliability=0.8, source_key="s4")
    assert rec.status == "blocked"
    assert "required-binding-missing" in rec.findings


def test_risk_brain_block_propagates():
    svc = ReintegrationReliabilityBaselinePreviewService()
    rec = svc.create(record_id="r5", workspace_id="ws-1", closed_episode=episode(risk_brain_blocked=True), current_reliability=0.8, source_key="s5")
    assert rec.risk_brain_blocked
    assert rec.status == "blocked"


def test_replay_and_workspace_isolation():
    svc = ReintegrationReliabilityBaselinePreviewService()
    svc.create(record_id="r6", workspace_id="ws-1", closed_episode=episode(), current_reliability=0.8, source_key="same")
    with pytest.raises(ValueError):
        svc.create(record_id="r7", workspace_id="ws-1", closed_episode=episode(), current_reliability=0.8, source_key="same")
    rec = svc.create(record_id="r8", workspace_id="ws-2", closed_episode=episode(), current_reliability=0.8, source_key="same")
    assert rec.status == "blocked"
    assert "workspace-mismatch" in rec.findings
