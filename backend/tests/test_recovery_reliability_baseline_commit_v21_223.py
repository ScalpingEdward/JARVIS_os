import pytest
from app.schemas.recovery_reliability_baseline_commit_v21_223 import BaselineCommitRequest
from app.services.recovery_reliability_baseline_commit_v21_223 import evaluate_baseline_commit, reset_seen_for_tests

@pytest.fixture(autouse=True)
def reset_seen():
    reset_seen_for_tests()

def req(**kw):
    data=dict(
        source_id='preview-222-a', source_state='approved-preview', source_human_approved=True,
        workspace_id='ws-1', previous_baseline_id='base-10', previous_baseline_version=10,
        previous_baseline_digest='dig-10', candidate_baseline_id='base-11', candidate_baseline_version=11,
        preview_digest='preview-dig', previous_value=0.70, candidate_value=0.73,
        rollback_baseline_id='base-10', rollback_baseline_version=10, rollback_baseline_digest='dig-10',
        recovery_sequence_digest='seq-dig', max_candidate_delta=0.05,
    )
    data.update(kw)
    return BaselineCommitRequest(**data)

def test_requires_human_approval():
    assert evaluate_baseline_commit(req()).state == 'review-required'
    assert evaluate_baseline_commit(req(), human_approved=True).state == 'committed'

def test_monotonic_version_required():
    assert evaluate_baseline_commit(req(candidate_baseline_version=12), human_approved=True).state == 'blocked'

def test_rollback_lineage_must_match_previous_baseline():
    assert evaluate_baseline_commit(req(rollback_baseline_digest='wrong'), human_approved=True).state == 'blocked'

def test_candidate_delta_limit_holds_for_review():
    d=evaluate_baseline_commit(req(candidate_value=0.90), human_approved=True)
    assert d.state == 'review-required'
    assert 'candidate-delta-limit-exceeded' in d.reasons

def test_candidate_id_must_be_new():
    assert evaluate_baseline_commit(req(candidate_baseline_id='base-10'), human_approved=True).state == 'blocked'

def test_duplicate_source_blocks_after_commit():
    assert evaluate_baseline_commit(req(), human_approved=True).state == 'committed'
    assert evaluate_baseline_commit(req(), human_approved=True).state == 'blocked'

def test_candidate_id_reuse_blocks():
    assert evaluate_baseline_commit(req(), human_approved=True).state == 'committed'
    second=req(source_id='preview-222-b', candidate_baseline_version=11)
    assert evaluate_baseline_commit(second, human_approved=True).state == 'blocked'

def test_invalid_source_blocks():
    assert evaluate_baseline_commit(req(source_state='review-required'), human_approved=True).state == 'blocked'

def test_risk_brain_hard_block():
    assert evaluate_baseline_commit(req(risk_brain_hard_block=True), human_approved=True).state == 'blocked'
