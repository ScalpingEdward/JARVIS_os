from app.services.reliability_adoption_drift_reconciliation import (
    DriftConsumer,
    ReliabilityAdoptionDriftRecord,
    ReliabilityAdoptionDriftReconciliationGovernance,
)


def rec(**overrides):
    data = dict(
        record_id="r1", workspace_id="w1", source_record_id="s1", baseline_id="b1",
        baseline_version=7, baseline_digest="digest7",
        affected_consumers=(DriftConsumer("c1", "version-mismatch", "b1", 7, "digest7"),),
        healthy_consumers=("c2", "c3"), consistency_score=0.67, blast_radius=0.33,
        residual_risk=0.20,
    )
    data.update(overrides)
    return ReliabilityAdoptionDriftRecord(**data)


def test_clean_readiness_lifecycle():
    g = ReliabilityAdoptionDriftReconciliationGovernance()
    r = g.create(rec(), source_state="drift-detected")
    assert r.state == "review-required"
    assert g.approve("r1", actor="human", human_approved=True).state == "reconciliation-ready"


def test_invalid_source_fails_closed():
    g = ReliabilityAdoptionDriftReconciliationGovernance()
    assert g.create(rec(), source_state="consistent").state == "blocked"


def test_consumer_overlap_fails_closed():
    g = ReliabilityAdoptionDriftReconciliationGovernance()
    assert g.create(rec(healthy_consumers=("c1", "c2")), source_state="drift-detected").state == "blocked"


def test_threshold_failure_fails_closed():
    g = ReliabilityAdoptionDriftReconciliationGovernance(max_blast_radius=0.2)
    assert g.create(rec(blast_radius=0.5), source_state="drift-detected").state == "blocked"


def test_expected_binding_mismatch_fails_closed():
    g = ReliabilityAdoptionDriftReconciliationGovernance()
    bad = DriftConsumer("c1", "digest-mismatch", "b1", 6, "old")
    assert g.create(rec(affected_consumers=(bad,)), source_state="drift-detected").state == "blocked"


def test_risk_brain_block_propagates():
    g = ReliabilityAdoptionDriftReconciliationGovernance()
    assert g.create(rec(risk_brain_blocked=True), source_state="drift-detected").state == "blocked"
