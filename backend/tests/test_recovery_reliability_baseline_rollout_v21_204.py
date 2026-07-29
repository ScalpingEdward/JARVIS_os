import pytest
from app.schemas.recovery_reliability_baseline_rollout_v21_204 import BaselineRolloutRequest, RolloutStage
from app.services.recovery_reliability_baseline_rollout_v21_204 import evaluate_rollout, reset_seen_sources_for_tests

@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_sources_for_tests()

def req(**kw):
    data=dict(source_id='commit-203-a', source_state='committed', source_human_approved=True, workspace_id='ws-1', baseline_id='base-a', baseline_version=9, baseline_digest='dig-9', rollback_version=8, rollback_value=0.72, candidate_consumers=['c1','c2','c3','c4'], stages=[RolloutStage(stage_index=1, consumer_ids=['c1'], max_stage_exposure=0.25), RolloutStage(stage_index=2, consumer_ids=['c2'], max_stage_exposure=0.25), RolloutStage(stage_index=3, consumer_ids=['c3'], max_stage_exposure=0.25), RolloutStage(stage_index=4, consumer_ids=['c4'], max_stage_exposure=0.25)])
    data.update(kw)
    return BaselineRolloutRequest(**data)

def test_requires_eligibility_approval():
    assert evaluate_rollout(req()).state == 'review-required'
    assert evaluate_rollout(req(), eligibility_approved=True).state == 'eligible'

def test_all_stages_approved_becomes_staged():
    d=evaluate_rollout(req(), eligibility_approved=True, approved_stage_indices=[1,2,3,4])
    assert d.state == 'staged'

def test_incomplete_coverage_blocks():
    stages=[RolloutStage(stage_index=1, consumer_ids=['c1','c2'], max_stage_exposure=0.5)]
    assert evaluate_rollout(req(stages=stages)).state == 'blocked'

def test_overlap_blocks():
    stages=[RolloutStage(stage_index=1, consumer_ids=['c1','c2'], max_stage_exposure=0.5),RolloutStage(stage_index=2, consumer_ids=['c2','c3','c4'], max_stage_exposure=0.75)]
    assert evaluate_rollout(req(stages=stages)).state == 'blocked'

def test_exposure_limit_requires_review():
    stages=[RolloutStage(stage_index=1, consumer_ids=['c1','c2'], max_stage_exposure=0.25),RolloutStage(stage_index=2, consumer_ids=['c3','c4'], max_stage_exposure=0.5)]
    d=evaluate_rollout(req(stages=stages), eligibility_approved=True)
    assert d.state == 'review-required'
    assert 'stage-exposure-limit-exceeded:1' in d.reasons

def test_invalid_source_blocks():
    assert evaluate_rollout(req(source_state='approved-preview')).state == 'blocked'

def test_duplicate_source_blocks_after_staged():
    assert evaluate_rollout(req(), eligibility_approved=True, approved_stage_indices=[1,2,3,4]).state == 'staged'
    assert evaluate_rollout(req(), eligibility_approved=True, approved_stage_indices=[1,2,3,4]).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_rollout(req(risk_brain_hard_block=True), eligibility_approved=True).state == 'blocked'
