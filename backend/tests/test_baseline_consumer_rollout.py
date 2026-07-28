import pytest
from app.services.baseline_consumer_rollout import BaselineConsumerRolloutService


def preview(**overrides):
    value = {
        "record_id": "preview-1",
        "workspace_id": "ws-1",
        "status": "approved-preview",
        "human_approved": True,
        "risk_brain_blocked": False,
        "blast_radius": 0.12,
        "residual_risk": 0.10,
        "baseline_id": "baseline-a",
        "baseline_version": 4,
    }
    value.update(overrides)
    return value


def test_clean_preview_can_be_approved_and_staged_to_active():
    svc = BaselineConsumerRolloutService()
    rec = svc.create(
        rollout_id="r1",
        workspace_id="ws-1",
        approved_preview=preview(),
        requested_consumers=["adapter-selection", "dispatch-planning"],
        source_key="s1",
        max_stage=2,
    )
    assert rec.status == "review-required"
    assert svc.approve("r1", human_approved=True).status == "approved"
    assert svc.advance_stage("r1", human_approved=True).status == "staged"
    final = svc.advance_stage("r1", human_approved=True)
    assert final.status == "active"
    assert final.rollout_stage == 2


def test_inactive_preview_blocks():
    svc = BaselineConsumerRolloutService()
    rec = svc.create(rollout_id="r2", workspace_id="ws-1", approved_preview=preview(status="review-required"), requested_consumers=["adapter-selection"], source_key="s2")
    assert rec.status == "blocked"


def test_blast_radius_and_residual_risk_fail_closed():
    svc = BaselineConsumerRolloutService()
    rec = svc.create(rollout_id="r3", workspace_id="ws-1", approved_preview=preview(blast_radius=0.5, residual_risk=0.4), requested_consumers=["worker-selection"], source_key="s3")
    assert rec.status == "blocked"
    assert "blast-radius-above-rollout-ceiling" in rec.findings
    assert "residual-risk-above-rollout-ceiling" in rec.findings


def test_unsupported_consumer_blocks():
    svc = BaselineConsumerRolloutService()
    rec = svc.create(rollout_id="r4", workspace_id="ws-1", approved_preview=preview(), requested_consumers=["trade-execution"], source_key="s4")
    assert rec.status == "blocked"
    assert any(item.startswith("unsupported-consumer:") for item in rec.findings)


def test_risk_brain_block_propagates():
    svc = BaselineConsumerRolloutService()
    rec = svc.create(rollout_id="r5", workspace_id="ws-1", approved_preview=preview(risk_brain_blocked=True), requested_consumers=["failover-health"], source_key="s5")
    assert rec.status == "blocked"
    assert rec.risk_brain_blocked


def test_replay_and_workspace_isolation():
    svc = BaselineConsumerRolloutService()
    svc.create(rollout_id="r6", workspace_id="ws-1", approved_preview=preview(), requested_consumers=["adapter-selection"], source_key="same")
    with pytest.raises(ValueError):
        svc.create(rollout_id="r7", workspace_id="ws-1", approved_preview=preview(), requested_consumers=["adapter-selection"], source_key="same")
    rec = svc.create(rollout_id="r8", workspace_id="ws-2", approved_preview=preview(), requested_consumers=["adapter-selection"], source_key="same")
    assert rec.status == "blocked"
    assert "workspace-mismatch" in rec.findings


def test_stage_advancement_requires_human_approval():
    svc = BaselineConsumerRolloutService()
    svc.create(rollout_id="r9", workspace_id="ws-1", approved_preview=preview(), requested_consumers=["recovery-readiness"], source_key="s9")
    svc.approve("r9", human_approved=True)
    with pytest.raises(ValueError):
        svc.advance_stage("r9", human_approved=False)
