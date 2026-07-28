import pytest

from app.services.reintegration_stability_observation import (
    ReintegrationStabilityObservationService,
    StabilitySample,
)


def reintegration(**overrides):
    value = {
        "record_id": "reintegration-1",
        "workspace_id": "ws-1",
        "status": "reintegrated",
        "human_approved": True,
        "risk_brain_blocked": False,
        "consumer_id": "adapter-selection",
        "baseline_id": "baseline-1",
        "baseline_version": 7,
        "baseline_digest": "baseline-digest",
    }
    value.update(overrides)
    return value


def samples(**overrides):
    values = {
        "consumer_healthy": True,
        "baseline_match": True,
        "dependency_satisfied": True,
        "latency_ms": 80.0,
        "confidence": 0.96,
        "freshness": 0.95,
        "error_rate": 0.0,
    }
    values.update(overrides)
    return [StabilitySample(**values) for _ in range(4)]


def test_clean_reintegration_requires_human_approval_then_stable():
    svc = ReintegrationStabilityObservationService()
    rec = svc.observe(record_id="r1", workspace_id="ws-1", reintegration=reintegration(), samples=samples(), source_key="s1")
    assert rec.status == "review-required"
    assert rec.aggregate_confidence >= 0.80
    with pytest.raises(ValueError):
        svc.approve("r1", human_approved=False)
    assert svc.approve("r1", human_approved=True).status == "stable"


def test_baseline_drift_degrades():
    svc = ReintegrationStabilityObservationService()
    rec = svc.observe(record_id="r2", workspace_id="ws-1", reintegration=reintegration(), samples=samples(baseline_match=False), source_key="s2")
    assert rec.status == "degraded"
    assert "baseline-drift-detected" in rec.findings


def test_latency_or_error_breach_degrades():
    svc = ReintegrationStabilityObservationService()
    rec = svc.observe(record_id="r3", workspace_id="ws-1", reintegration=reintegration(), samples=samples(latency_ms=1500.0, error_rate=0.10), source_key="s3")
    assert rec.status == "degraded"
    assert "latency-threshold-breach" in rec.findings
    assert "error-rate-threshold-breach" in rec.findings


def test_invalid_reintegration_admission_blocks_progress():
    svc = ReintegrationStabilityObservationService()
    rec = svc.observe(record_id="r4", workspace_id="ws-1", reintegration=reintegration(status="staged"), samples=samples(), source_key="s4")
    assert rec.status == "degraded"
    assert "consumer-not-reintegrated" in rec.findings


def test_risk_brain_block_propagates():
    svc = ReintegrationStabilityObservationService()
    rec = svc.observe(record_id="r5", workspace_id="ws-1", reintegration=reintegration(risk_brain_blocked=True), samples=samples(), source_key="s5")
    assert rec.risk_brain_blocked
    assert rec.status == "degraded"


def test_replay_workspace_and_empty_samples_fail_closed():
    svc = ReintegrationStabilityObservationService()
    svc.observe(record_id="r6", workspace_id="ws-1", reintegration=reintegration(), samples=samples(), source_key="same")
    with pytest.raises(ValueError):
        svc.observe(record_id="r7", workspace_id="ws-1", reintegration=reintegration(), samples=samples(), source_key="same")
    rec = svc.observe(record_id="r8", workspace_id="ws-2", reintegration=reintegration(), samples=samples(), source_key="same")
    assert rec.status == "degraded"
    assert "workspace-mismatch" in rec.findings
    with pytest.raises(ValueError):
        svc.observe(record_id="r9", workspace_id="ws-1", reintegration=reintegration(), samples=[], source_key="empty")
