import pytest
from app.schemas.recovery_reliability_feedback_impact_preview_v21_222 import FeedbackImpactSimulationRequest
from app.services.recovery_reliability_feedback_impact_preview_v21_222 import simulate_feedback_impact, reset_seen_sources_for_tests

@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_sources_for_tests()

def req(**kw):
    data = dict(
        source_id='feedback-221-a', source_state='approved-feedback', source_human_approved=True,
        workspace_id='ws-1', baseline_id='base-a', baseline_version=12, baseline_digest='dig-12',
        recovery_sequence_digest='seq-12', current_value=0.62, feedback_adjustment=0.03,
        current_score=0.81, current_rank=4, current_failover_readiness=0.77,
        current_recovery_readiness=0.83, projected_score_delta=0.04, projected_rank_delta=-1,
        projected_failover_delta=0.05, projected_recovery_delta=0.03,
        blast_radius=0.20, residual_risk=0.10,
    )
    data.update(kw)
    return FeedbackImpactSimulationRequest(**data)

def test_requires_human_approval():
    assert simulate_feedback_impact(req()).state == 'review-required'
    assert simulate_feedback_impact(req(), human_approved=True).state == 'approved-preview'

def test_candidate_and_projection_are_deterministic():
    d = simulate_feedback_impact(req())
    assert d.candidate_value == 0.65
    assert d.projected_score == 0.85
    assert d.projected_rank == 3
    assert d.projected_failover_readiness == 0.82
    assert d.projected_recovery_readiness == 0.86

def test_projection_clamps_to_valid_range():
    d = simulate_feedback_impact(req(current_value=0.99, feedback_adjustment=0.05, current_score=0.98, projected_score_delta=0.5))
    assert d.candidate_value == 1.0
    assert d.projected_score == 1.0

def test_blast_radius_limit_requires_review():
    d = simulate_feedback_impact(req(blast_radius=0.8), human_approved=True)
    assert d.state == 'review-required'
    assert 'blast-radius-limit-exceeded' in d.reasons

def test_residual_risk_limit_requires_review():
    d = simulate_feedback_impact(req(residual_risk=0.9), human_approved=True)
    assert d.state == 'review-required'

def test_invalid_source_blocks():
    assert simulate_feedback_impact(req(source_state='closed'), human_approved=True).state == 'blocked'

def test_duplicate_source_blocks_after_approval():
    assert simulate_feedback_impact(req(), human_approved=True).state == 'approved-preview'
    assert simulate_feedback_impact(req(), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert simulate_feedback_impact(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'
