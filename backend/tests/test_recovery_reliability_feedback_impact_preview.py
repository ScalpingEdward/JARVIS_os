from app.services.recovery_reliability_feedback_impact_preview import (
    RecoveryReliabilityFeedbackImpactGovernance,
    RecoveryReliabilityImpactPreview,
)


def record(**kw):
    data = dict(
        record_id="r1", workspace_id="w1", source_record_id="s1", baseline_id="b1",
        baseline_version=4, baseline_digest="digest", current_value=0.70,
        proposed_adjustment=0.03, candidate_value=0.73, score_impact=0.04,
        rank_impact=0.02, failover_tendency_impact=-0.01,
        recovery_readiness_impact=0.03, blast_radius=0.10, residual_risk=0.12,
    )
    data.update(kw)
    return RecoveryReliabilityImpactPreview(**data)


def test_clean_preview_lifecycle():
    g = RecoveryReliabilityFeedbackImpactGovernance()
    r = g.create(record(), source_state="approved-feedback", source_human_approved=True)
    assert r.state == "review-required"
    assert g.approve_preview("r1", actor="human", human_approved=True).state == "approved-preview"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityFeedbackImpactGovernance()
    assert g.create(record(), source_state="closed", source_human_approved=True).state == "blocked"


def test_adjustment_bound_fails_closed():
    g = RecoveryReliabilityFeedbackImpactGovernance()
    assert g.create(record(proposed_adjustment=0.08, candidate_value=0.78), source_state="approved-feedback", source_human_approved=True).state == "blocked"


def test_candidate_math_mismatch_fails_closed():
    g = RecoveryReliabilityFeedbackImpactGovernance()
    assert g.create(record(candidate_value=0.75), source_state="approved-feedback", source_human_approved=True).state == "blocked"


def test_risk_limits_fail_closed():
    g = RecoveryReliabilityFeedbackImpactGovernance()
    assert g.create(record(blast_radius=0.40), source_state="approved-feedback", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityFeedbackImpactGovernance()
    assert g.create(record(risk_brain_blocked=True), source_state="approved-feedback", source_human_approved=True).state == "blocked"
