from app.services.recovery_reliability_baseline_rollout_v21_184 import (
    RecoveryReliabilityBaselineRolloutV21184Governance,
    RecoveryReliabilityRolloutV21184Record,
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
        rollback_value=0.70,
        candidate_consumers=("c1", "c2", "c3", "c4"),
        stages=[RolloutStage(1, ("c1", "c2")), RolloutStage(2, ("c3", "c4"))],
        max_stage_fraction=0.50,
    )
    data.update(overrides)
    return RecoveryReliabilityRolloutV21184Record(**data)


def test_clean_rollout_lifecycle():
    g = RecoveryReliabilityBaselineRolloutV21184Governance()
    r = g.create(record(), source_state="committed", source_human_approved=True)
    assert r.state == "review-required"
    assert g.approve_eligibility("r1", actor="human", human_approved=True).state == "eligible"
    assert g.approve_stage("r1", stage=1, actor="human", human_approved=True).state == "staged"
    r = g.approve_stage("r1", stage=2, actor="human", human_approved=True)
    assert all(stage.approved for stage in r.stages)


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityBaselineRolloutV21184Governance()
    assert g.create(record(), source_state="approved-preview", source_human_approved=True).state == "blocked"


def test_stage_exposure_limit_fails_closed():
    g = RecoveryReliabilityBaselineRolloutV21184Governance()
    r = record(stages=[RolloutStage(1, ("c1", "c2", "c3")), RolloutStage(2, ("c4",))])
    assert g.create(r, source_state="committed", source_human_approved=True).state == "blocked"


def test_overlap_fails_closed():
    g = RecoveryReliabilityBaselineRolloutV21184Governance()
    r = record(stages=[RolloutStage(1, ("c1", "c2")), RolloutStage(2, ("c2", "c3", "c4"))])
    assert g.create(r, source_state="committed", source_human_approved=True).state == "blocked"


def test_stage_order_fails_closed():
    g = RecoveryReliabilityBaselineRolloutV21184Governance()
    g.create(record(), source_state="committed", source_human_approved=True)
    g.approve_eligibility("r1", actor="human", human_approved=True)
    assert g.approve_stage("r1", stage=2, actor="human", human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityBaselineRolloutV21184Governance()
    assert g.create(record(risk_brain_blocked=True), source_state="committed", source_human_approved=True).state == "blocked"
