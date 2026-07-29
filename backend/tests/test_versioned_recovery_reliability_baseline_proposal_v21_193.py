from app.services.versioned_recovery_reliability_baseline_proposal_v21_193 import (
    RecoveryReliabilityBaselineProposal,
    VersionedRecoveryReliabilityBaselineCommitGovernance,
)


def record(**kw):
    data = dict(
        record_id="r1",
        workspace_id="w1",
        source_record_id="s1",
        preview_id="p1",
        baseline_id="b1",
        previous_version=7,
        proposed_version=8,
        previous_value=0.72,
        candidate_value=0.75,
        previous_digest="prev-digest",
        rollback_version=7,
        rollback_value=0.72,
    )
    data.update(kw)
    return RecoveryReliabilityBaselineProposal(**data)


def propose(g, r=None, **kw):
    return g.propose(
        r or record(),
        source_state=kw.get("source_state", "approved-preview"),
        source_human_approved=kw.get("source_human_approved", True),
        preview_previous_value=kw.get("preview_previous_value", 0.72),
        preview_candidate_value=kw.get("preview_candidate_value", 0.75),
    )


def test_valid_proposal_requires_human_commit():
    g = VersionedRecoveryReliabilityBaselineCommitGovernance()
    r = propose(g)
    assert r.state == "review-required"
    assert r.proposed_version == r.previous_version + 1
    assert r.rollback_version == r.previous_version
    assert g.commit("r1", actor="human", human_approved=True).state == "committed"


def test_invalid_source_fails_closed():
    g = VersionedRecoveryReliabilityBaselineCommitGovernance()
    assert propose(g, source_state="approved-feedback").state == "blocked"


def test_non_monotone_version_fails_closed():
    g = VersionedRecoveryReliabilityBaselineCommitGovernance()
    assert propose(g, record(proposed_version=9)).state == "blocked"


def test_excessive_candidate_delta_fails_closed():
    g = VersionedRecoveryReliabilityBaselineCommitGovernance()
    r = record(candidate_value=0.90)
    assert propose(g, r, preview_candidate_value=0.90).state == "blocked"


def test_preview_value_mismatch_fails_closed():
    g = VersionedRecoveryReliabilityBaselineCommitGovernance()
    assert propose(g, preview_candidate_value=0.74).state == "blocked"


def test_rollback_binding_mismatch_fails_closed():
    g = VersionedRecoveryReliabilityBaselineCommitGovernance()
    assert propose(g, record(rollback_version=6)).state == "blocked"


def test_duplicate_source_fails_closed():
    g = VersionedRecoveryReliabilityBaselineCommitGovernance()
    propose(g)
    r2 = record(record_id="r2", preview_id="p2")
    assert propose(g, r2).state == "blocked"


def test_risk_brain_fails_closed():
    g = VersionedRecoveryReliabilityBaselineCommitGovernance()
    assert propose(g, record(risk_brain_blocked=True)).state == "blocked"
