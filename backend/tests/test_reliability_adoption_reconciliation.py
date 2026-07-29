from app.services.reliability_adoption_reconciliation import (
    RecoveryStep,
    ReconciliationAuthorizationRecord,
    ReliabilityAdoptionReconciliationGovernance,
)


def record(**overrides):
    data = dict(
        record_id="r1", workspace_id="w1", source_record_id="s1", baseline_id="b1",
        baseline_version=5, baseline_digest="abc", affected_consumers=("c1", "c2"),
        healthy_consumers=("c3",),
        steps=[RecoveryStep(1, "c1", "version-drift"), RecoveryStep(2, "c2", "digest-drift")],
        blast_radius=0.3, residual_risk=0.2,
    )
    data.update(overrides)
    return ReconciliationAuthorizationRecord(**data)


def test_clean_authorization_and_ordered_recovery():
    g = ReliabilityAdoptionReconciliationGovernance()
    r = g.create(record(), source_state="reconciliation-ready", source_human_approved=True)
    assert r.state == "review-required"
    assert g.authorize("r1", actor="human", human_approved=True).state == "authorized"
    assert g.approve_step("r1", order=1, actor="human", human_approved=True).state == "staged"
    r = g.approve_step("r1", order=2, actor="human", human_approved=True)
    assert r.state == "recovery-ready"
    assert all(s.approved for s in r.steps)


def test_invalid_source_fails_closed():
    g = ReliabilityAdoptionReconciliationGovernance()
    assert g.create(record(), source_state="drift-detected", source_human_approved=True).state == "blocked"


def test_step_order_fails_closed():
    g = ReliabilityAdoptionReconciliationGovernance()
    g.create(record(), source_state="reconciliation-ready", source_human_approved=True)
    g.authorize("r1", actor="human", human_approved=True)
    assert g.approve_step("r1", order=2, actor="human", human_approved=True).state == "blocked"


def test_consumer_overlap_fails_closed():
    g = ReliabilityAdoptionReconciliationGovernance()
    assert g.create(record(healthy_consumers=("c2", "c3")), source_state="reconciliation-ready", source_human_approved=True).state == "blocked"


def test_threshold_fails_closed():
    g = ReliabilityAdoptionReconciliationGovernance(max_residual_risk=0.25)
    assert g.create(record(residual_risk=0.5), source_state="reconciliation-ready", source_human_approved=True).state == "blocked"


def test_risk_brain_block_propagates():
    g = ReliabilityAdoptionReconciliationGovernance()
    assert g.create(record(risk_brain_blocked=True), source_state="reconciliation-ready", source_human_approved=True).state == "blocked"
