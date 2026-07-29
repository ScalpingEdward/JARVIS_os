import pytest
from app.schemas.recovery_reliability_baseline_commit_v21_213 import BaselineCommitRequest
from app.services.recovery_reliability_baseline_commit_v21_213 import evaluate_baseline_commit, reset_seen_for_tests

@pytest.fixture(autouse=True)
def reset_seen(): reset_seen_for_tests()

def req(**kw):
    data=dict(source_id='preview-212-a', source_state='approved-preview', source_human_approved=True, workspace_id='ws-1', preview_id='pv-1', previous_baseline_id='base-10', previous_version=10, previous_value=0.70, previous_digest='dig-10', candidate_baseline_id='base-11', candidate_version=11, candidate_value=0.73, candidate_preview_digest='preview-dig', rollback_version=10, rollback_value=0.70)
    data.update(kw); return BaselineCommitRequest(**data)

def test_requires_human_approval():
    assert evaluate_baseline_commit(req()).state == 'review-required'
    assert evaluate_baseline_commit(req(), human_approved=True).state == 'committed'

def test_version_must_increment_exactly_one():
    assert evaluate_baseline_commit(req(candidate_version=12), human_approved=True).state == 'blocked'

def test_rollback_must_match_previous_baseline():
    assert evaluate_baseline_commit(req(rollback_value=0.60), human_approved=True).state == 'blocked'

def test_delta_limit_blocks():
    assert evaluate_baseline_commit(req(candidate_value=0.80), human_approved=True).state == 'blocked'

def test_candidate_id_reuse_blocks():
    assert evaluate_baseline_commit(req(candidate_baseline_id='base-10'), human_approved=True).state == 'blocked'

def test_invalid_source_blocks():
    assert evaluate_baseline_commit(req(source_state='review-required'), human_approved=True).state == 'blocked'

def test_duplicate_source_and_preview_block_after_commit():
    assert evaluate_baseline_commit(req(), human_approved=True).state == 'committed'
    assert evaluate_baseline_commit(req(), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_baseline_commit(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'
