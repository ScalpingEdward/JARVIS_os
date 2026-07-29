import pytest
from app.schemas.recovery_reliability_feedback_impact_preview_v21_212 import FeedbackImpactPreviewRequest
from app.services.recovery_reliability_feedback_impact_preview_v21_212 import simulate_feedback_impact, reset_seen_sources_for_tests

@pytest.fixture(autouse=True)
def reset_seen(): reset_seen_sources_for_tests()

def req(**kw):
    data=dict(source_id='feedback-211-a', source_state='approved-feedback', source_human_approved=True, workspace_id='ws-1', baseline_id='base-a', baseline_version=10, baseline_digest='dig-10', current_value=0.70, feedback_adjustment=0.03, score_impact=0.08, rank_impact=0.02, failover_impact=0.01, recovery_readiness_impact=0.04, blast_radius=0.20, residual_risk=0.10)
    data.update(kw); return FeedbackImpactPreviewRequest(**data)

def test_requires_human_approval_for_preview():
    assert simulate_feedback_impact(req()).state == 'review-required'
    assert simulate_feedback_impact(req(), human_approved=True).state == 'approved-preview'

def test_candidate_value_is_deterministic():
    d=simulate_feedback_impact(req())
    assert d.candidate_value == 0.73

def test_invalid_source_blocks():
    assert simulate_feedback_impact(req(source_state='closed')).state == 'blocked'

def test_candidate_out_of_range_blocks():
    d=simulate_feedback_impact(req(current_value=0.99, feedback_adjustment=0.05))
    assert d.state == 'blocked'

def test_blast_radius_holds_for_review():
    assert simulate_feedback_impact(req(blast_radius=0.8), human_approved=True).state == 'review-required'

def test_residual_risk_holds_for_review():
    assert simulate_feedback_impact(req(residual_risk=0.8), human_approved=True).state == 'review-required'

def test_duplicate_source_blocks_after_approval():
    assert simulate_feedback_impact(req(), human_approved=True).state == 'approved-preview'
    assert simulate_feedback_impact(req(), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert simulate_feedback_impact(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'

def test_preview_digest_is_deterministic():
    assert simulate_feedback_impact(req()).preview_digest == simulate_feedback_impact(req()).preview_digest
