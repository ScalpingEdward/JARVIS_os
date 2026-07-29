from app.services.recovery_reliability_adoption_drift_reconciliation_readiness_v21187 import (
    DriftConsumer,
    ReconciliationReadinessRecord,
    RecoveryReliabilityAdoptionDriftReconciliationReadinessGovernance,
)


def record(**kw):
    data = dict(
        record_id="r1", workspace_id="w1", source_record_id="s1", baseline_id="b1",
        baseline_version=7, baseline_digest="digest",
        affected_consumers=(DriftConsumer("c1", "baseline-mismatch", 0.4),),
        healthy_consumers=("c2", "c3"), blast_radius=0.25, residual_risk=0.2,
    )
    data.update(kw)
    return ReconciliationReadinessRecord(**data)


def test_clean_readiness_lifecycle():
    g = RecoveryReliabilityAdoptionDriftReconciliationReadinessGovernance()
    r = g.evaluate(record(), source_state="drift-detected", source_human_approved=True)
    assert r.state == "review-required"
    assert r.readiness_score >= 0.55
    assert g.approve("r1", actor="human", human_approved=True).state == "reconciliation-ready"


def test_invalid_source_fails_closed():
    g = RecoveryReliabilityAdoptionDriftReconciliationReadinessGovernance()
    assert g.evaluate(record(), source_state="consistent", source_human_approved=True).state == "blocked"


def test_consumer_overlap_fails_closed():
    g = RecoveryReliabilityAdoptionDriftReconciliationReadinessGovernance()
    r = record(healthy_consumers=("c1", "c2"))
    assert g.evaluate(r, source_state="drift-detected", source_human_approved=True).state == "blocked"


def test_blast_radius_limit_fails_closed():
    g = RecoveryReliabilityAdoptionDriftReconciliationReadinessGovernance()
    r = record(blast_radius=0.8)
    assert g.evaluate(r, source_state="drift-detected", source_human_approved=True).state == "blocked"


def test_low_readiness_requires_block():
    g = RecoveryReliabilityAdoptionDriftReconciliationReadinessGovernance()
    r = record(
        affected_consumers=(DriftConsumer("c1", "severe-drift", 1.0),),
        blast_radius=0.5, residual_risk=0.35,
    )
    g.evaluate(r, source_state="drift-detected", source_human_approved=True)
    assert g.approve("r1", actor="human", human_approved=True, minimum_readiness=0.8).state == "blocked"


def test_risk_brain_fails_closed():
    g = RecoveryReliabilityAdoptionDriftReconciliationReadinessGovernance()
    assert g.evaluate(record(risk_brain_blocked=True), source_state="drift-detected", source_human_approved=True).state == "blocked"
