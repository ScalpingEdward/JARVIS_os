from app.services.recovery_reliability_reconciliation_authorization import (
    ReconciliationAuthorizationRecord,
    RecoveryReliabilityReconciliationAuthorizationGovernance,
    RecoveryStep,
)


def record(**overrides):
    data = dict(
        record_id="r1", workspace_id="w1", source_record_id="s1", baseline_id="b1",
        baseline_version=5, baseline_digest="digest", affected_consumers=("c1", "c2"),
        healthy_consumers=("c3",), recovery_steps=[RecoveryStep(1, "c1"), RecoveryStep(2, "c2")],
        blast_radius=0.25, residual_risk=0.2,
    )
    data.update(overrides)
    return ReconciliationAuthorizationRecord(**data)


def test_clean_ordered_recovery_lifecycle():
    g = RecoveryReliabilityReconciliationAuthorizationGovernance()
    r = g.create(record(), source_state="reconciliation-ready", source_human_approved=True)
    assert r.state == "review-required"
    assert g.authorize("r1", actor="human", human_approved=True).state == "authorized"
    assert g.approve_step("r1", order=1, actor="human", human_approved=True).state == "staged"
    assert g.approve_step("r1", order=2, actor="human", human_approved=True).state == "recovery-ready"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityReconciliationAuthorizationGovernance()
    assert g.create(record(), source_state="drift-detected", source_human_approved=True).state == "blocked"


def test_out_of_order_step_fails_closed():
    g = RecoveryReliabilityReconciliationAuthorizationGovernance()
    g.create(record(), source_state="reconciliation-ready", source_human_approved=True)
    g.authorize("r1", actor="human", human_approved=True)
    assert g.approve_step("r1", order=2, actor="human", human_approved=True).state == "blocked"


def test_consumer_overlap_fails_closed():
    g = RecoveryReliabilityReconciliationAuthorizationGovernance()
    r = record(healthy_consumers=("c2", "c3"))
    assert g.create(r, source_state="reconciliation-ready", source_human_approved=True).state == "blocked"


def test_risk_limits_fail_closed():
    g = RecoveryReliabilityReconciliationAuthorizationGovernance(max_blast_radius=0.2)
    assert g.create(record(blast_radius=0.3), source_state="reconciliation-ready", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityReconciliationAuthorizationGovernance()
    assert g.create(record(risk_brain_blocked=True), source_state="reconciliation-ready", source_human_approved=True).state == "blocked"
