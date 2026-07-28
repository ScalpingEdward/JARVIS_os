import pytest
from app.services.containment_effectiveness_observation import (
    ContainmentEffectivenessObservationService,
    ContainmentObservationSample,
)


def containment(**overrides):
    value = {
        "record_id": "contain-1",
        "workspace_id": "ws-1",
        "status": "fallback-ready",
        "human_approved": True,
        "risk_brain_blocked": False,
        "quarantined_consumer": "worker-selection",
    }
    value.update(overrides)
    return value


def sample(**overrides):
    value = {
        "sample_id": "s1",
        "capability": "selection",
        "available": True,
        "fallback_healthy": True,
        "dependency_satisfied": True,
        "latency_ms": 100.0,
        "confidence": 0.95,
        "freshness": 0.95,
    }
    value.update(overrides)
    return ContainmentObservationSample(**value)


def test_clean_observation_requires_human_approval():
    svc = ContainmentEffectivenessObservationService()
    rec = svc.observe(record_id="r1", workspace_id="ws-1", containment=containment(), samples=[sample()], source_key="k1")
    assert rec.status == "review-required"
    with pytest.raises(ValueError):
        svc.approve_resolution_readiness("r1", human_approved=False)
    assert svc.approve_resolution_readiness("r1", human_approved=True).status == "resolution-ready"


def test_capability_failure_degrades():
    svc = ContainmentEffectivenessObservationService()
    rec = svc.observe(record_id="r2", workspace_id="ws-1", containment=containment(), samples=[sample(available=False)], source_key="k2")
    assert rec.status == "degraded"
    assert "capability-availability-below-floor" in rec.findings


def test_wrong_admission_state_degrades():
    svc = ContainmentEffectivenessObservationService()
    rec = svc.observe(record_id="r3", workspace_id="ws-1", containment=containment(status="approved"), samples=[sample()], source_key="k3")
    assert rec.status == "degraded"
    assert "containment-not-fallback-ready" in rec.findings


def test_risk_brain_block_propagates():
    svc = ContainmentEffectivenessObservationService()
    rec = svc.observe(record_id="r4", workspace_id="ws-1", containment=containment(risk_brain_blocked=True), samples=[sample()], source_key="k4")
    assert rec.risk_brain_blocked
    assert rec.status == "degraded"


def test_replay_and_workspace_isolation():
    svc = ContainmentEffectivenessObservationService()
    svc.observe(record_id="r5", workspace_id="ws-1", containment=containment(), samples=[sample()], source_key="same")
    with pytest.raises(ValueError):
        svc.observe(record_id="r6", workspace_id="ws-1", containment=containment(), samples=[sample()], source_key="same")
    rec = svc.observe(record_id="r7", workspace_id="ws-2", containment=containment(), samples=[sample()], source_key="same")
    assert rec.status == "degraded"
    assert "workspace-mismatch" in rec.findings


def test_empty_samples_fail_closed():
    svc = ContainmentEffectivenessObservationService()
    rec = svc.observe(record_id="r8", workspace_id="ws-1", containment=containment(), samples=[], source_key="k8")
    assert rec.status == "degraded"
    assert "no-observation-samples" in rec.findings
