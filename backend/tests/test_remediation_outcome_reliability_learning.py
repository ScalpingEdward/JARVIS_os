import pytest

from app.services.remediation_outcome_reliability_learning import RemediationOutcomeReliabilityLearningService


def closed_episode(**overrides):
    value = {
        "record_id": "closure-1",
        "workspace_id": "ws-1",
        "status": "closed",
        "human_approved": True,
        "risk_brain_blocked": False,
        "baseline_id": "baseline-a",
        "baseline_version": 3,
        "baseline_digest": "digest-a",
        "stability_score": 0.94,
        "aggregate_confidence": 0.92,
        "residual_risk": 0.08,
        "reconciliation_score": 1.0,
    }
    value.update(overrides)
    return value


def test_clean_closed_episode_creates_reviewable_learning_feedback():
    svc = RemediationOutcomeReliabilityLearningService()
    rec = svc.create(
        record_id="r1",
        workspace_id="ws-1",
        remediation_episode_id="episode-1",
        closed_episode=closed_episode(),
        baseline_before=0.80,
        source_key="s1",
    )
    assert rec.status == "review-required"
    assert rec.proposed_baseline <= 0.85
    with pytest.raises(ValueError):
        svc.approve("r1", human_approved=False)
    assert svc.approve("r1", human_approved=True).status == "approved-feedback"


def test_feedback_adjustment_is_bounded():
    svc = RemediationOutcomeReliabilityLearningService()
    rec = svc.create(
        record_id="r2",
        workspace_id="ws-1",
        remediation_episode_id="episode-2",
        closed_episode=closed_episode(stability_score=1.0, aggregate_confidence=1.0, residual_risk=0.0),
        baseline_before=0.50,
        source_key="s2",
        max_adjustment=0.05,
    )
    assert rec.proposed_baseline == 0.55


def test_invalid_admission_blocks():
    svc = RemediationOutcomeReliabilityLearningService()
    rec = svc.create(
        record_id="r3",
        workspace_id="ws-1",
        remediation_episode_id="episode-3",
        closed_episode=closed_episode(status="review-required", human_approved=False),
        baseline_before=0.80,
        source_key="s3",
    )
    assert rec.status == "blocked"


def test_low_confidence_and_high_risk_block():
    svc = RemediationOutcomeReliabilityLearningService()
    rec = svc.create(
        record_id="r4",
        workspace_id="ws-1",
        remediation_episode_id="episode-4",
        closed_episode=closed_episode(aggregate_confidence=0.70, residual_risk=0.30),
        baseline_before=0.80,
        source_key="s4",
    )
    assert rec.status == "blocked"
    assert "confidence-below-learning-floor" in rec.findings
    assert "residual-risk-above-learning-ceiling" in rec.findings


def test_missing_baseline_binding_blocks():
    svc = RemediationOutcomeReliabilityLearningService()
    rec = svc.create(
        record_id="r5",
        workspace_id="ws-1",
        remediation_episode_id="episode-5",
        closed_episode=closed_episode(baseline_id="", baseline_version=0, baseline_digest=""),
        baseline_before=0.80,
        source_key="s5",
    )
    assert rec.status == "blocked"
    assert "baseline-binding-missing" in rec.findings


def test_risk_brain_block_propagates():
    svc = RemediationOutcomeReliabilityLearningService()
    rec = svc.create(
        record_id="r6",
        workspace_id="ws-1",
        remediation_episode_id="episode-6",
        closed_episode=closed_episode(risk_brain_blocked=True),
        baseline_before=0.80,
        source_key="s6",
    )
    assert rec.risk_brain_blocked
    assert rec.status == "blocked"


def test_replay_and_workspace_isolation():
    svc = RemediationOutcomeReliabilityLearningService()
    svc.create(
        record_id="r7",
        workspace_id="ws-1",
        remediation_episode_id="episode-7",
        closed_episode=closed_episode(),
        baseline_before=0.80,
        source_key="same",
    )
    with pytest.raises(ValueError):
        svc.create(
            record_id="r8",
            workspace_id="ws-1",
            remediation_episode_id="episode-8",
            closed_episode=closed_episode(),
            baseline_before=0.80,
            source_key="same",
        )
    rec = svc.create(
        record_id="r9",
        workspace_id="ws-2",
        remediation_episode_id="episode-9",
        closed_episode=closed_episode(),
        baseline_before=0.80,
        source_key="same",
    )
    assert rec.status == "blocked"
    assert "workspace-mismatch" in rec.findings
