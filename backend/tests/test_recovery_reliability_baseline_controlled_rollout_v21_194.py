from app.services.recovery_reliability_baseline_controlled_rollout_v21_194 import (
    RecoveryReliabilityBaselineControlledRolloutGovernance,
    RolloutEligibilityRecord,
    RolloutStage,
)


def record(stages=None, **kw):
    data = dict(
        record_id="r1",
        workspace_id="w1",
        source_record_id="s1",
        baseline_id="b1",
        baseline_version=8,
        baseline_digest="digest",
        rollback_version=7,
        rollback_value=0.72,
        candidate_consumers=("c1", "c2", "c3"),
        stages=stages or [
            RolloutStage(1, ("c1",), 0.25),
            RolloutStage(2, ("c2", "c3"), 0.50),
        ],
    )
    data.update(kw)
    return RolloutEligibilityRecord(**data)


def test_valid_rollout_requires_human_eligibility_and_ordered_stage_approval():
    g = RecoveryReliabilityBaselineControlledRolloutGovernance()
    r = g.create(record(), source_state="committed", source_human_approved=True)
    assert r.state == "review-required"
    assert g.approve_eligibility("r1", actor="human", human_approved=True).state == "eligible"
    assert g.approve_stage("r1", order=1, actor="human", human_approved=True).state == "staged"
    assert g.approve_stage("r1", order=2, actor="human", human_approved=True).state == "staged"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityBaselineControlledRolloutGovernance()
    assert g.create(record(), source_state="approved-preview", source_human_approved=True).state == "blocked"


def test_overlapping_consumers_fail_closed():
    g = RecoveryReliabilityBaselineControlledRolloutGovernance()
    stages = [RolloutStage(1, ("c1", "c2"), 0.25), RolloutStage(2, ("c2", "c3"), 0.50)]
    assert g.create(record(stages=stages), source_state="committed", source_human_approved=True).state == "blocked"


def test_exposure_limit_fails_closed():
    g = RecoveryReliabilityBaselineControlledRolloutGovernance(max_stage_exposure=0.50)
    stages = [RolloutStage(1, ("c1",), 0.60), RolloutStage(2, ("c2", "c3"), 0.50)]
    assert g.create(record(stages=stages), source_state="committed", source_human_approved=True).state == "blocked"


def test_out_of_order_stage_fails_closed():
    g = RecoveryReliabilityBaselineControlledRolloutGovernance()
    g.create(record(), source_state="committed", source_human_approved=True)
    g.approve_eligibility("r1", actor="human", human_approved=True)
    assert g.approve_stage("r1", order=2, actor="human", human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityBaselineControlledRolloutGovernance()
    assert g.create(record(risk_brain_blocked=True), source_state="committed", source_human_approved=True).state == "blocked"
