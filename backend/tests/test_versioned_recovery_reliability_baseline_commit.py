from app.services.versioned_recovery_reliability_baseline_commit import (
    RecoveryReliabilityBaselineProposal,
    VersionedRecoveryReliabilityBaselineCommitGovernance,
)


def record(**kw):
    data = dict(
        record_id="r1", workspace_id="w1", source_record_id="s1", baseline_id="b1",
        previous_version=4, candidate_version=5, previous_value=0.72, candidate_value=0.75,
        preview_digest="preview", rollback_version=4, rollback_value=0.72,
    )
    data.update(kw)
    return RecoveryReliabilityBaselineProposal(**data)


def test_clean_commit_requires_human_approval():
    g = VersionedRecoveryReliabilityBaselineCommitGovernance()
    r = g.create(record(), source_state="approved-preview", source_human_approved=True)
    assert r.state == "review-required"
    assert g.commit("r1", actor="human", human_approved=True).state == "committed"


def test_invalid_source_fails_closed():
    g = VersionedRecoveryReliabilityBaselineCommitGovernance()
    assert g.create(record(), source_state="approved-feedback", source_human_approved=True).state == "blocked"


def test_non_monotone_version_fails_closed():
    g = VersionedRecoveryReliabilityBaselineCommitGovernance()
    assert g.create(record(candidate_version=6), source_state="approved-preview", source_human_approved=True).state == "blocked"


def test_delta_limit_fails_closed():
    g = VersionedRecoveryReliabilityBaselineCommitGovernance()
    assert g.create(record(candidate_value=0.80), source_state="approved-preview", source_human_approved=True).state == "blocked"


def test_rollback_binding_must_match_previous():
    g = VersionedRecoveryReliabilityBaselineCommitGovernance()
    assert g.create(record(rollback_value=0.71), source_state="approved-preview", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = VersionedRecoveryReliabilityBaselineCommitGovernance()
    assert g.create(record(risk_brain_blocked=True), source_state="approved-preview", source_human_approved=True).state == "blocked"
