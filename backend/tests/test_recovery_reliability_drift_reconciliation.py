from app.services.recovery_reliability_drift_reconciliation import (
    DriftFinding,
    ReconciliationReadinessRecord,
    RecoveryReliabilityDriftReconciliationGovernance,
)


def record(**kw):
    data = dict(
        record_id="r1", workspace_id="w1", source_record_id="s1", baseline_id="b1",
        baseline_version=5, baseline_digest="digest", affected_consumers=("c1",),
        healthy_consumers=("c2",), findings=(DriftFinding("c1", "baseline-mismatch", 0.10),),
        blast_radius=0.10, residual_risk=0.10,
    )
    data.update(kw)
    return ReconciliationReadinessRecord(**data)


def test_clean_readiness_requires_human_approval():
    g = RecoveryReliabilityDriftReconciliationGovernance()
    r = g.create(record(), source_state="drift-detected", source_human_approved=True)
    assert r.state == "review-required"
    assert r.readiness_score >= r.readiness_threshold
    assert g.approve_readiness("r1", actor="human", human_approved=True).state == "reconciliation-ready"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityDriftReconciliationGovernance()
    assert g.create(record(), source_state="consistent", source_human_approved=True).state == "blocked"


def test_consumer_overlap_fails_closed():
    g = RecoveryReliabilityDriftReconciliationGovernance()
    r = record(healthy_consumers=("c1", "c2"))
    assert g.create(r, source_state="drift-detected", source_human_approved=True).state == "blocked"


def test_risk_limit_fails_closed():
    g = RecoveryReliabilityDriftReconciliationGovernance()
    r = record(blast_radius=0.90)
    assert g.create(r, source_state="drift-detected", source_human_approved=True).state == "blocked"


def test_readiness_threshold_fails_closed():
    g = RecoveryReliabilityDriftReconciliationGovernance()
    r = record(findings=(DriftFinding("c1", "severe-drift", 1.0),), blast_radius=0.50, residual_risk=0.35)
    g.create(r, source_state="drift-detected", source_human_approved=True)
    assert g.approve_readiness("r1", actor="human", human_approved=True).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityDriftReconciliationGovernance()
    assert g.create(record(risk_brain_blocked=True), source_state="drift-detected", source_human_approved=True).state == "blocked"
