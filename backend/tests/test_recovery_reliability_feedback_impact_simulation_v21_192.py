from app.services.recovery_reliability_feedback_impact_simulation_v21_192 import (
    RecoveryReliabilityFeedbackImpactSimulationGovernance,
    RecoveryReliabilityImpactPreview,
)


def record(**kw):
    data = dict(
        record_id="r1",
        workspace_id="w1",
        source_record_id="s1",
        baseline_id="b1",
        baseline_version=8,
        baseline_digest="digest",
        current_value=0.70,
        feedback_adjustment=0.03,
        score_impact=0.08,
        rank_impact=0.04,
        failover_tendency_impact=-0.03,
        recovery_readiness_impact=0.06,
        blast_radius=0.20,
        residual_risk=0.12,
    )
    data.update(kw)
    return RecoveryReliabilityImpactPreview(**data)


def test_clean_preview_requires_human_approval():
    g = RecoveryReliabilityFeedbackImpactSimulationGovernance()
    r = g.simulate(record(), source_state="approved-feedback", source_human_approved=True)
    assert r.state == "review-required"
    assert r.candidate_value == 0.73
    assert g.approve_preview("r1", actor="human", human_approved=True).state == "approved-preview"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityFeedbackImpactSimulationGovernance()
    assert g.simulate(record(), source_state="closed", source_human_approved=True).state == "blocked"


def test_excessive_adjustment_fails_closed():
    g = RecoveryReliabilityFeedbackImpactSimulationGovernance()
    assert g.simulate(record(feedback_adjustment=0.06), source_state="approved-feedback", source_human_approved=True).state == "blocked"


def test_candidate_out_of_range_fails_closed():
    g = RecoveryReliabilityFeedbackImpactSimulationGovernance()
    assert g.simulate(record(current_value=0.99, feedback_adjustment=0.03), source_state="approved-feedback", source_human_approved=True).state == "blocked"


def test_risk_limits_fail_closed():
    g = RecoveryReliabilityFeedbackImpactSimulationGovernance()
    assert g.simulate(record(residual_risk=0.50), source_state="approved-feedback", source_human_approved=True).state == "blocked"


def test_duplicate_source_fails_closed():
    g = RecoveryReliabilityFeedbackImpactSimulationGovernance()
    g.simulate(record(), source_state="approved-feedback", source_human_approved=True)
    r2 = record(record_id="r2")
    assert g.simulate(r2, source_state="approved-feedback", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityFeedbackImpactSimulationGovernance()
    assert g.simulate(record(risk_brain_blocked=True), source_state="approved-feedback", source_human_approved=True).state == "blocked"
