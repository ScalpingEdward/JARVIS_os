from app.services.recovery_reliability_outcome_learning_v21_191 import (
    RecoveryReliabilityLearningRecord,
    RecoveryReliabilityOutcomeLearningGovernance,
)


def record(**kw):
    data = dict(
        record_id="r1",
        workspace_id="w1",
        source_record_id="s1",
        baseline_id="b1",
        baseline_version=8,
        baseline_digest="digest",
        stability_score=0.94,
        aggregate_confidence=0.92,
        recovery_quality=0.93,
        residual_risk=0.08,
        proposed_adjustment=0.02,
    )
    data.update(kw)
    return RecoveryReliabilityLearningRecord(**data)


def test_clean_learning_requires_human_feedback_approval():
    g = RecoveryReliabilityOutcomeLearningGovernance()
    r = g.learn(record(), source_state="closed", source_human_approved=True)
    assert r.state == "review-required"
    assert r.learning_score > 0.90
    assert g.approve_feedback("r1", actor="human", human_approved=True).state == "approved-feedback"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityOutcomeLearningGovernance()
    assert g.learn(record(), source_state="completed", source_human_approved=True).state == "blocked"


def test_excessive_feedback_adjustment_fails_closed():
    g = RecoveryReliabilityOutcomeLearningGovernance()
    assert g.learn(record(proposed_adjustment=0.06), source_state="closed", source_human_approved=True).state == "blocked"


def test_weak_recovery_evidence_fails_closed():
    g = RecoveryReliabilityOutcomeLearningGovernance()
    assert g.learn(record(stability_score=0.70), source_state="closed", source_human_approved=True).state == "blocked"


def test_duplicate_source_fails_closed():
    g = RecoveryReliabilityOutcomeLearningGovernance()
    first = g.learn(record(), source_state="closed", source_human_approved=True)
    assert first.state == "review-required"
    second = record(record_id="r2")
    assert g.learn(second, source_state="closed", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityOutcomeLearningGovernance()
    assert g.learn(record(risk_brain_blocked=True), source_state="closed", source_human_approved=True).state == "blocked"
