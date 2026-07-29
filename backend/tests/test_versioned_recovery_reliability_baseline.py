from app.services.versioned_recovery_reliability_baseline import (
    RecoveryReliabilityBaselineProposal,
    VersionedRecoveryReliabilityBaselineGovernance,
)


def proposal(**overrides):
    data = dict(
        record_id="r1",
        workspace_id="w1",
        source_record_id="s1",
        preview_id="p1",
        baseline_id="b1",
        previous_version=4,
        candidate_version=5,
        previous_value=0.70,
        candidate_value=0.73,
        previous_digest="digest-v4",
        rollback_version=4,
        rollback_value=0.70,
    )
    data.update(overrides)
    return RecoveryReliabilityBaselineProposal(**data)


def test_clean_commit_lifecycle():
    g = VersionedRecoveryReliabilityBaselineGovernance()
    r = g.create(proposal(), source_state="approved-preview", source_human_approved=True)
    assert r.state == "review-required"
    r = g.approve_commit("r1", actor="human", human_approved=True)
    assert r.state == "committed"
    assert r.approved_by == "human"


def test_invalid_source_fails_closed():
    g = VersionedRecoveryReliabilityBaselineGovernance()
    assert g.create(proposal(), source_state="approved-feedback", source_human_approved=True).state == "blocked"


def test_version_gap_fails_closed():
    g = VersionedRecoveryReliabilityBaselineGovernance()
    assert g.create(proposal(candidate_version=6), source_state="approved-preview", source_human_approved=True).state == "blocked"


def test_rollback_binding_fails_closed():
    g = VersionedRecoveryReliabilityBaselineGovernance()
    assert g.create(proposal(rollback_value=0.65), source_state="approved-preview", source_human_approved=True).state == "blocked"


def test_excessive_delta_fails_closed():
    g = VersionedRecoveryReliabilityBaselineGovernance()
    assert g.create(proposal(candidate_value=0.80), source_state="approved-preview", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = VersionedRecoveryReliabilityBaselineGovernance()
    assert g.create(proposal(risk_brain_blocked=True), source_state="approved-preview", source_human_approved=True).state == "blocked"
