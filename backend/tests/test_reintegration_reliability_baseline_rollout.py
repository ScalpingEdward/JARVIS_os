import pytest
from app.services.reintegration_reliability_baseline_rollout import ReintegrationReliabilityBaselineRolloutService


def preview(**overrides):
    value = {
        "record_id": "p1", "workspace_id": "ws-1", "status": "approved-preview",
        "human_approved": True, "risk_brain_blocked": False,
        "consumer_id": "adapter-selection", "baseline_id": "rel-main",
        "candidate_baseline": 0.91,
    }
    value.update(overrides)
    return value


def test_commit_then_staged_rollout_requires_human_each_time():
    svc = ReintegrationReliabilityBaselineRolloutService()
    rec = svc.create(record_id="r1", workspace_id="ws-1", approved_preview=preview(), consumers=["adapter-selection", "worker-selection"], source_key="s1", max_stage=2)
    assert rec.status == "review-required"
    with pytest.raises(ValueError):
        svc.approve_commit("r1", human_approved=False)
    assert svc.approve_commit("r1", human_approved=True).status == "committed"
    with pytest.raises(ValueError):
        svc.advance_stage("r1", human_approved=False)
    assert svc.advance_stage("r1", human_approved=True).status == "staged"
    assert svc.advance_stage("r1", human_approved=True).status == "active"


def test_unsupported_consumer_blocks():
    svc = ReintegrationReliabilityBaselineRolloutService()
    rec = svc.create(record_id="r2", workspace_id="ws-1", approved_preview=preview(), consumers=["unknown-consumer"], source_key="s2")
    assert rec.status == "blocked"
    assert any(x.startswith("unsupported-consumer") for x in rec.findings)


def test_invalid_preview_or_workspace_blocks():
    svc = ReintegrationReliabilityBaselineRolloutService()
    rec = svc.create(record_id="r3", workspace_id="ws-2", approved_preview=preview(status="review-required"), consumers=["adapter-selection"], source_key="s3")
    assert rec.status == "blocked"
    assert "workspace-mismatch" in rec.findings
    assert "preview-not-approved" in rec.findings


def test_risk_brain_block_propagates():
    svc = ReintegrationReliabilityBaselineRolloutService()
    rec = svc.create(record_id="r4", workspace_id="ws-1", approved_preview=preview(risk_brain_blocked=True), consumers=["adapter-selection"], source_key="s4")
    assert rec.risk_brain_blocked
    assert rec.status == "blocked"


def test_version_increments_after_commit():
    svc = ReintegrationReliabilityBaselineRolloutService()
    a = svc.create(record_id="r5", workspace_id="ws-1", approved_preview=preview(), consumers=["adapter-selection"], source_key="s5")
    assert a.baseline_version == 1
    svc.approve_commit("r5", human_approved=True)
    b = svc.create(record_id="r6", workspace_id="ws-1", approved_preview=preview(candidate_baseline=0.92), consumers=["adapter-selection"], source_key="s6")
    assert b.baseline_version == 2


def test_replay_protection_and_empty_consumers():
    svc = ReintegrationReliabilityBaselineRolloutService()
    svc.create(record_id="r7", workspace_id="ws-1", approved_preview=preview(), consumers=["adapter-selection"], source_key="same")
    with pytest.raises(ValueError):
        svc.create(record_id="r8", workspace_id="ws-1", approved_preview=preview(), consumers=["adapter-selection"], source_key="same")
    rec = svc.create(record_id="r9", workspace_id="ws-2", approved_preview=preview(workspace_id="ws-2"), consumers=[], source_key="same")
    assert rec.status == "blocked"
    assert "no-consumers" in rec.findings
