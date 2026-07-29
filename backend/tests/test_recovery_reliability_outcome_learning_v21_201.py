import pytest
from app.schemas.recovery_reliability_outcome_learning_v21_201 import RecoveryOutcomeLearningRequest
from app.services.recovery_reliability_outcome_learning_v21_201 import evaluate_outcome_learning, reset_seen_sources_for_tests

@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_sources_for_tests()

def req(**kw):
    data=dict(
        source_id='closure-200-a', source_state='closed', source_human_approved=True,
        workspace_id='ws-1', baseline_id='base-a', baseline_version=9,
        baseline_digest='dig-9', stability_score=0.94, aggregate_confidence=0.92,
        recovery_quality=0.93, residual_risk=0.10, proposed_feedback_adjustment=0.02,
        risk_brain_hard_block=False,
    )
    data.update(kw)
    return RecoveryOutcomeLearningRequest(**data)

def test_requires_human_approval_before_feedback():
    assert evaluate_outcome_learning(req()).state == 'review-required'
    assert evaluate_outcome_learning(req(), human_approved=True).state == 'approved-feedback'

def test_invalid_source_blocks():
    assert evaluate_outcome_learning(req(source_state='completed')).state == 'blocked'

def test_weak_stability_requires_review():
    d = evaluate_outcome_learning(req(stability_score=0.70), human_approved=True)
    assert d.state == 'review-required'
    assert 'weak-stability-evidence' in d.reasons

def test_weak_confidence_requires_review():
    d = evaluate_outcome_learning(req(aggregate_confidence=0.60), human_approved=True)
    assert d.state == 'review-required'

def test_high_residual_risk_requires_review():
    d = evaluate_outcome_learning(req(residual_risk=0.40), human_approved=True)
    assert d.state == 'review-required'

def test_adjustment_is_bounded_by_schema_and_service():
    d = evaluate_outcome_learning(req(proposed_feedback_adjustment=0.05), human_approved=True)
    assert d.bounded_feedback_adjustment == 0.05

def test_duplicate_source_blocks_after_approval():
    assert evaluate_outcome_learning(req(), human_approved=True).state == 'approved-feedback'
    assert evaluate_outcome_learning(req(), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_outcome_learning(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'
