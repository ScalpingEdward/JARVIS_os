import pytest
from app.schemas.recovery_reliability_feedback_impact_preview_v21_202 import FeedbackImpactPreviewRequest
from app.services.recovery_reliability_feedback_impact_preview_v21_202 import simulate_feedback_impact, reset_seen_sources_for_tests

@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_sources_for_tests()

def req(**kw):
    data=dict(
        source_id='feedback-201-a', source_state='approved-feedback', source_human_approved=True,
        workspace_id='ws-1', baseline_id='base-a', baseline_version=9, baseline_digest='dig-9',
        current_value=0.70, feedback_adjustment=0.03,
        expected_score_impact=0.08, expected_rank_impact=0.04,
        expected_failover_tendency_impact=-0.03, expected_recovery_readiness_impact=0.07,
        blast_radius=0.20, residual_risk=0.15,
    )
    data.update(kw)
    return FeedbackImpactPreviewRequest(**data)

def test_requires_human_approval_for_preview():
    assert simulate_feedback_impact(req()).state == 'review-required'
    d = simulate_feedback_impact(req(), human_approved=True)
    assert d.state == 'approved-preview'
    assert d.candidate_value == 0.73

def test_invalid_source_blocks():
    assert simulate_feedback_impact(req(source_state='closed'), human_approved=True).state == 'blocked'

def test_candidate_range_blocks():
    d = simulate_feedback_impact(req(current_value=0.99, feedback_adjustment=0.05), human_approved=True)
    assert d.state == 'blocked'
    assert 'candidate-value-out-of-range' in d.reasons

def test_blast_radius_requires_review():
    d = simulate_feedback_impact(req(blast_radius=0.8), human_approved=True)
    assert d.state == 'review-required'
    assert 'blast-radius-limit-exceeded' in d.reasons

def test_residual_risk_requires_review():
    d = simulate_feedback_impact(req(residual_risk=0.7), human_approved=True)
    assert d.state == 'review-required'
    assert 'residual-risk-limit-exceeded' in d.reasons

def test_duplicate_source_blocks_after_approval():
    assert simulate_feedback_impact(req(), human_approved=True).state == 'approved-preview'
    assert simulate_feedback_impact(req(), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert simulate_feedback_impact(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'

def test_digests_are_deterministic():
    a = simulate_feedback_impact(req())
    b = simulate_feedback_impact(req())
    assert a.preview_digest == b.preview_digest
    assert a.audit_digest == b.audit_digest
