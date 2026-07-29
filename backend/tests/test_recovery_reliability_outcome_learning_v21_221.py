import pytest
from app.schemas.recovery_reliability_outcome_learning_v21_221 import RecoveryOutcomeLearningRequest
from app.services.recovery_reliability_outcome_learning_v21_221 import evaluate_outcome_learning, reset_seen_sources_for_tests

@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_sources_for_tests()

def req(**kw):
    data=dict(source_id='closed-220-a', source_state='closed', source_human_approved=True, workspace_id='ws-1', baseline_id='base-a', baseline_version=11, baseline_digest='dig-11', recovery_sequence_digest='seq-11', stability_score=0.94, mean_confidence=0.92, mean_recovery_quality=0.93, residual_risk=0.08, requested_feedback_adjustment=0.02)
    data.update(kw)
    return RecoveryOutcomeLearningRequest(**data)

def test_requires_human_approval():
    assert evaluate_outcome_learning(req()).state == 'review-required'
    assert evaluate_outcome_learning(req(), human_approved=True).state == 'approved-feedback'

def test_low_learning_score_requires_review():
    d = evaluate_outcome_learning(req(stability_score=0.4, mean_confidence=0.4, mean_recovery_quality=0.4, residual_risk=0.6), human_approved=True)
    assert d.state == 'review-required'

def test_invalid_source_blocks():
    assert evaluate_outcome_learning(req(source_state='completed'), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_outcome_learning(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'

def test_duplicate_source_blocks_after_approval():
    assert evaluate_outcome_learning(req(), human_approved=True).state == 'approved-feedback'
    assert evaluate_outcome_learning(req(), human_approved=True).state == 'blocked'

def test_feedback_adjustment_is_returned_only_when_approved():
    d = evaluate_outcome_learning(req(requested_feedback_adjustment=-0.03), human_approved=True)
    assert d.approved_feedback_adjustment == -0.03
