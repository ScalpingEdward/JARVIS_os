import pytest
from app.services.incident_episode_closure import IncidentEpisodeClosureService


def stable(**overrides):
    value = {
        "record_id": "stability-1", "workspace_id": "ws-1", "status": "stable",
        "human_approved": True, "risk_brain_blocked": False,
        "aggregate_confidence": 0.94, "residual_risk": 0.08,
        "primary_adapter_id": "adapter-a", "primary_worker_id": "worker-a", "gateway_id": "gateway-a",
    }
    value.update(overrides)
    return value


def test_stable_episode_can_be_human_closed():
    svc = IncidentEpisodeClosureService()
    rec = svc.create(closure_id="c1", workspace_id="ws-1", incident_id="i1", stable_observation=stable(), baseline_before=0.80, source_key="s1")
    assert rec.status == "review-required"
    assert rec.proposed_baseline <= 0.85
    with pytest.raises(ValueError):
        svc.approve("c1", human_approved=False)
    assert svc.approve("c1", human_approved=True).status == "closed"


def test_baseline_feedback_is_bounded():
    svc = IncidentEpisodeClosureService()
    rec = svc.create(closure_id="c2", workspace_id="ws-1", incident_id="i2", stable_observation=stable(aggregate_confidence=1.0, residual_risk=0.0), baseline_before=0.50, source_key="s2", max_adjustment=0.05)
    assert rec.proposed_baseline == 0.55


def test_unstable_or_unapproved_evidence_blocks():
    svc = IncidentEpisodeClosureService()
    rec = svc.create(closure_id="c3", workspace_id="ws-1", incident_id="i3", stable_observation=stable(status="approved", human_approved=False), baseline_before=0.8, source_key="s3")
    assert rec.status == "blocked"


def test_risk_brain_block_propagates():
    svc = IncidentEpisodeClosureService()
    rec = svc.create(closure_id="c4", workspace_id="ws-1", incident_id="i4", stable_observation=stable(risk_brain_blocked=True), baseline_before=0.8, source_key="s4")
    assert rec.risk_brain_blocked
    assert rec.status == "blocked"


def test_low_confidence_or_high_residual_risk_blocks():
    svc = IncidentEpisodeClosureService()
    rec = svc.create(closure_id="c5", workspace_id="ws-1", incident_id="i5", stable_observation=stable(aggregate_confidence=0.70, residual_risk=0.30), baseline_before=0.8, source_key="s5")
    assert rec.status == "blocked"
    assert "confidence-below-closure-floor" in rec.findings


def test_replay_and_workspace_isolation():
    svc = IncidentEpisodeClosureService()
    svc.create(closure_id="c6", workspace_id="ws-1", incident_id="i6", stable_observation=stable(), baseline_before=0.8, source_key="same")
    with pytest.raises(ValueError):
        svc.create(closure_id="c7", workspace_id="ws-1", incident_id="i7", stable_observation=stable(), baseline_before=0.8, source_key="same")
    rec = svc.create(closure_id="c8", workspace_id="ws-2", incident_id="i8", stable_observation=stable(), baseline_before=0.8, source_key="same")
    assert rec.status == "blocked"
    assert "workspace-mismatch" in rec.findings
