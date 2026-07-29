from app.services.recovery_reliability_baseline_rollout import (
    RecoveryReliabilityBaselineRolloutGovernance,
    RecoveryReliabilityRolloutRecord,
    RolloutStage,
)


def record(**overrides):
    data = dict(
        record_id="r1",
        workspace_id="w1",
        source_record_id="s1",
        baseline_id="b1",
        baseline_version=5,
        baseline_digest="digest",
        rollback_version=4,
        rollback_value=0.72,
        candidate_consumers=("c1", "c2"),
        stages=[RolloutStage(1, ("c1",)), RolloutStage(2, ("c2",))],
    )
    data.update(overrides)
    return RecoveryReliabilityRolloutRecord(**data)


def test_clean_rollout_lifecycle():
    g = RecoveryReliabilityBaselineRolloutGovernance()
    r = g.create(record(), source_state="committed", source_human_approved=True)
    assert r.state == "review-required"
    assert g.approve_eligibility("r1", actor="human", human_approved=True).state == "eligible"
    assert g.approve_stage("r1", stage=1, actor="human", human_approved=True).state == "staged"
    r = g.approve_stage("r1", stage=2, actor="human", human_approved=True)
    assert all(s.approved for s in r.stages)


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityBaselineRolloutGovernance()
    assert g.create(record(), source_state="approved-preview", source_human_approved=True).state == "blocked"


def test_bad_rollback_binding_fails_closed():
    g = RecoveryReliabilityBaselineRolloutGovernance()
    assert g.create(record(rollback_version=3), source_state="committed", source_human_approved=True).state == "blocked"


def test_stage_order_fails_closed():
    g = RecoveryReliabilityBaselineRolloutGovernance()
    g.create(record(), source_state="committed", source_human_approved=True)
    g.approve_eligibility("r1", actor="human", human_approved=True)
    assert g.approve_stage("r1", stage=2, actor="human", human_approved=True).state == "blocked"


def test_consumer_overlap_fails_closed():
    g = RecoveryReliabilityBaselineRolloutGovernance()
    r = record(stages=[RolloutStage(1, ("c1",)), RolloutStage(2, ("c1", "c2"))])
    assert g.create(r, source_state="committed", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityBaselineRolloutGovernance()
    assert g.create(record(risk_brain_blocked=True), source_state="committed", source_human_approved=True).state == "blocked"
