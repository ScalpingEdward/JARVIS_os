from app.services.recovery_reliability_reconciliation_authorization_v21_188 import (
    RecoveryAuthorizationRecord188,
    RecoveryReliabilityReconciliationAuthorizationGovernance188,
    RecoveryStep188,
)


def record(**kw):
    data = dict(
        record_id="r1",
        workspace_id="w1",
        source_record_id="s1",
        baseline_id="b1",
        baseline_version=8,
        baseline_digest="digest",
        affected_consumers=("c1", "c2"),
        healthy_consumers=("c3",),
        steps=[RecoveryStep188(1, "c1", "baseline-mismatch"), RecoveryStep188(2, "c2", "unhealthy")],
        blast_radius=0.25,
        residual_risk=0.15,
    )
    data.update(kw)
    return RecoveryAuthorizationRecord188(**data)


def test_clean_ordered_authorization_flow():
    g = RecoveryReliabilityReconciliationAuthorizationGovernance188()
    r = g.create(record(), source_state="reconciliation-ready", source_human_approved=True)
    assert r.state == "review-required"
    assert g.authorize("r1", actor="human", human_approved=True).state == "authorized"
    assert g.approve_step("r1", order=1, actor="human", human_approved=True).state == "staged"
    assert g.approve_step("r1", order=2, actor="human", human_approved=True).state == "recovery-ready"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityReconciliationAuthorizationGovernance188()
    assert g.create(record(), source_state="consistent", source_human_approved=True).state == "blocked"


def test_overlap_fails_closed():
    g = RecoveryReliabilityReconciliationAuthorizationGovernance188()
    assert g.create(record(healthy_consumers=("c2", "c3")), source_state="reconciliation-ready", source_human_approved=True).state == "blocked"


def test_out_of_order_step_fails_closed():
    g = RecoveryReliabilityReconciliationAuthorizationGovernance188()
    g.create(record(), source_state="reconciliation-ready", source_human_approved=True)
    g.authorize("r1", actor="human", human_approved=True)
    assert g.approve_step("r1", order=2, actor="human", human_approved=True).state == "blocked"


def test_risk_limit_fails_closed():
    g = RecoveryReliabilityReconciliationAuthorizationGovernance188()
    assert g.create(record(blast_radius=0.8), source_state="reconciliation-ready", source_human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityReconciliationAuthorizationGovernance188()
    assert g.create(record(risk_brain_blocked=True), source_state="reconciliation-ready", source_human_approved=True).state == "blocked"
