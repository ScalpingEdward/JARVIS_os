import pytest
from app.schemas.recovery_reliability_outcome_learning_v21_211 import OutcomeLearningRequest
from app.services.recovery_reliability_outcome_learning_v21_211 import evaluate_outcome_learning, reset_seen_sources_for_tests

@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_sources_for_tests()

def req(**kw):
    data=dict(source_id='closed-210-a', source_state='closed', source_human_approved=True, workspace_id='ws-1', baseline_id='base-a', baseline_version=10, baseline_digest='dig-10', stability_score=0.95, aggregate_confidence=0.92, recovery_quality=0.94, residual_risk=0.08, current_baseline_value=0.70)
    data.update(kw)
    return OutcomeLearningRequest(**data)

def test_requires_human_approval_for_feedback():
    assert evaluate_outcome_learning(req()).state == 'review-required'
    assert evaluate_outcome_learning(req(), human_approved=True).state == 'approved-feedback'

def test_feedback_is_bounded():
    d = evaluate_outcome_learning(req(), human_approved=True)
    assert abs(d.feedback_adjustment) <= 0.05

def test_weak_learning_evidence_requires_review():
    d = evaluate_outcome_learning(req(stability_score=0.4, aggregate_confidence=0.4, recovery_quality=0.4, residual_risk=0.1), human_approved=True)
    assert d.state == 'review-required'

def test_high_residual_risk_requires_review():
    assert evaluate_outcome_learning(req(residual_risk=0.5), human_approved=True).state == 'review-required'

def test_invalid_source_blocks():
    assert evaluate_outcome_learning(req(source_state='degraded'), human_approved=True).state == 'blocked'

def test_duplicate_source_blocks_after_approval():
    assert evaluate_outcome_learning(req(), human_approved=True).state == 'approved-feedback'
    assert evaluate_outcome_learning(req(), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_outcome_learning(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'

def test_digest_is_deterministic():
    d1 = evaluate_outcome_learning(req())
    d2 = evaluate_outcome_learning(req())
    assert d1.feedback_digest == d2.feedback_digest
