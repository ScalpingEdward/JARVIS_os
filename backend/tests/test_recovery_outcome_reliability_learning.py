from app.services.recovery_outcome_reliability_learning import (
    RecoveryOutcomeFeedbackRecord,
    RecoveryOutcomeReliabilityLearningGovernance,
)


def record(**overrides):
    data = dict(
        record_id="r1", workspace_id="w1", source_record_id="s1", baseline_id="b1",
        baseline_version=4, baseline_digest="digest", stability_score=0.92,
        aggregate_confidence=0.9, recovery_quality=0.88, residual_risk=0.08,
        previous_reliability=0.80,
    )
    data.update(overrides)
    return RecoveryOutcomeFeedbackRecord(**data)


def test_clean_feedback_lifecycle():
    g = RecoveryOutcomeReliabilityLearningGovernance()
    r = g.create(record(), source_state="closed", source_human_approved=True)
    assert r.state == "review-required"
    assert 0.0 <= r.learning_score <= 1.0
    assert abs(r.proposed_reliability - r.previous_reliability) <= 0.05
    assert g.approve_feedback("r1", actor="human", human_approved=True).state == "approved-feedback"


def test_invalid_source_fails_closed():
    g = RecoveryOutcomeReliabilityLearningGovernance()
    assert g.create(record(), source_state="completed", source_human_approved=True).state == "blocked"


def test_invalid_metric_fails_closed():
    g = RecoveryOutcomeReliabilityLearningGovernance()
    assert g.create(record(stability_score=1.2), source_state="closed", source_human_approved=True).state == "blocked"


def test_adjustment_is_bounded():
    g = RecoveryOutcomeReliabilityLearningGovernance()
    r = g.create(record(stability_score=1.0, aggregate_confidence=1.0, recovery_quality=1.0, residual_risk=0.0, previous_reliability=0.4), source_state="closed", source_human_approved=True)
    assert r.proposed_reliability == 0.45


def test_risk_brain_fails_closed():
    g = RecoveryOutcomeReliabilityLearningGovernance()
    assert g.create(record(risk_brain_blocked=True), source_state="closed", source_human_approved=True).state == "blocked"
