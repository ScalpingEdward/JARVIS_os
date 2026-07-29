from app.services.recovery_reliability_outcome_learning import (
    RecoveryReliabilityOutcomeLearningGovernance,
    RecoveryReliabilityOutcomeLearningRecord,
)


def record(**overrides):
    data = dict(
        record_id="r1",
        workspace_id="w1",
        source_record_id="s1",
        baseline_id="b1",
        baseline_version=5,
        baseline_digest="digest",
        stability_score=0.90,
        aggregate_confidence=0.85,
        recovery_quality=0.88,
        residual_risk=0.10,
        requested_adjustment=0.02,
    )
    data.update(overrides)
    return RecoveryReliabilityOutcomeLearningRecord(**data)


def test_clean_learning_lifecycle():
    g = RecoveryReliabilityOutcomeLearningGovernance()
    r = g.create(record(), source_state="closed", source_human_approved=True)
    assert r.state == "review-required"
    assert r.learning_score >= g.MIN_EVIDENCE_SCORE
    r = g.approve_feedback("r1", actor="human", human_approved=True)
    assert r.state == "approved-feedback"
    assert r.approved_adjustment == 0.02


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityOutcomeLearningGovernance()
    assert g.create(record(), source_state="completed", source_human_approved=True).state == "blocked"


def test_excessive_adjustment_fails_closed():
    g = RecoveryReliabilityOutcomeLearningGovernance()
    assert g.create(record(requested_adjustment=0.051), source_state="closed", source_human_approved=True).state == "blocked"


def test_poor_evidence_fails_closed():
    g = RecoveryReliabilityOutcomeLearningGovernance()
    r = record(stability_score=0.20, aggregate_confidence=0.20, recovery_quality=0.20, residual_risk=0.90)
    assert g.create(r, source_state="closed", source_human_approved=True).state == "blocked"


def test_duplicate_source_fails_closed():
    g = RecoveryReliabilityOutcomeLearningGovernance()
    g.create(record(), source_state="closed", source_human_approved=True)
    r2 = record(record_id="r2")
    assert g.create(r2, source_state="closed", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityOutcomeLearningGovernance()
    assert g.create(record(risk_brain_blocked=True), source_state="closed", source_human_approved=True).state == "blocked"
