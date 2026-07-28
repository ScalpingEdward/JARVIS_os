import pytest

from app.services.quarantine_episode_closure import QuarantineEpisodeClosureService


def stable(**overrides):
    value = {
        "record_id": "stability-1",
        "workspace_id": "ws-1",
        "status": "stable",
        "human_approved": True,
        "risk_brain_blocked": False,
        "consumer_id": "consumer-a",
        "baseline_id": "baseline-a",
        "baseline_version": "7",
        "baseline_digest": "baseline-digest",
        "aggregate_confidence": 0.95,
        "residual_risk": 0.05,
    }
    value.update(overrides)
    return value


def test_clean_episode_can_close_after_human_approval():
    svc = QuarantineEpisodeClosureService()
    rec = svc.create(record_id="c1", workspace_id="ws-1", quarantine_id="q1", stable_evidence=stable(), current_reliability=0.80, source_key="s1")
    assert rec.status == "review-required"
    assert rec.proposed_reliability <= 0.85
    with pytest.raises(ValueError):
        svc.approve("c1", human_approved=False)
    assert svc.approve("c1", human_approved=True).status == "closed"


def test_feedback_adjustment_is_bounded():
    svc = QuarantineEpisodeClosureService()
    rec = svc.create(record_id="c2", workspace_id="ws-1", quarantine_id="q2", stable_evidence=stable(aggregate_confidence=1.0, residual_risk=0.0), current_reliability=0.50, source_key="s2", max_adjustment=0.05)
    assert rec.proposed_reliability == 0.55


def test_non_stable_evidence_blocks():
    svc = QuarantineEpisodeClosureService()
    rec = svc.create(record_id="c3", workspace_id="ws-1", quarantine_id="q3", stable_evidence=stable(status="degraded"), current_reliability=0.8, source_key="s3")
    assert rec.status == "blocked"
    assert "reintegration-not-stable" in rec.findings


def test_low_confidence_or_high_risk_blocks():
    svc = QuarantineEpisodeClosureService()
    rec = svc.create(record_id="c4", workspace_id="ws-1", quarantine_id="q4", stable_evidence=stable(aggregate_confidence=0.70, residual_risk=0.30), current_reliability=0.8, source_key="s4")
    assert rec.status == "blocked"
    assert "confidence-below-closure-floor" in rec.findings
    assert "residual-risk-above-closure-ceiling" in rec.findings


def test_missing_binding_blocks():
    svc = QuarantineEpisodeClosureService()
    rec = svc.create(record_id="c5", workspace_id="ws-1", quarantine_id="q5", stable_evidence=stable(baseline_digest=""), current_reliability=0.8, source_key="s5")
    assert rec.status == "blocked"
    assert "required-binding-missing" in rec.findings


def test_risk_brain_block_propagates():
    svc = QuarantineEpisodeClosureService()
    rec = svc.create(record_id="c6", workspace_id="ws-1", quarantine_id="q6", stable_evidence=stable(risk_brain_blocked=True), current_reliability=0.8, source_key="s6")
    assert rec.risk_brain_blocked
    assert rec.status == "blocked"


def test_replay_and_workspace_isolation():
    svc = QuarantineEpisodeClosureService()
    svc.create(record_id="c7", workspace_id="ws-1", quarantine_id="q7", stable_evidence=stable(), current_reliability=0.8, source_key="same")
    with pytest.raises(ValueError):
        svc.create(record_id="c8", workspace_id="ws-1", quarantine_id="q8", stable_evidence=stable(), current_reliability=0.8, source_key="same")
    rec = svc.create(record_id="c9", workspace_id="ws-2", quarantine_id="q9", stable_evidence=stable(), current_reliability=0.8, source_key="same")
    assert rec.status == "blocked"
    assert "workspace-mismatch" in rec.findings
