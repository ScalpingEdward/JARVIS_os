import pytest
from app.services.reintegration_baseline_adoption_consistency import (
    AdoptionReceipt,
    ReintegrationBaselineAdoptionConsistencyService,
)


def rollout(**overrides):
    value = {
        "record_id": "rollout-1",
        "workspace_id": "ws-1",
        "status": "active",
        "human_approved": True,
        "risk_brain_blocked": False,
        "baseline_id": "baseline-r1",
        "baseline_version": 3,
        "baseline_digest": "digest-v3",
        "consumers": ["adapter-selection", "worker-selection", "dispatch-planning"],
    }
    value.update(overrides)
    return value


def receipt(consumer, **overrides):
    value = {
        "receipt_id": f"receipt-{consumer}",
        "consumer_id": consumer,
        "baseline_id": "baseline-r1",
        "baseline_version": 3,
        "baseline_digest": "digest-v3",
        "consumer_state": "adopted",
        "source_digest": f"source-{consumer}",
    }
    value.update(overrides)
    return AdoptionReceipt(**value)


def clean_receipts():
    return [
        receipt("adapter-selection"),
        receipt("worker-selection"),
        receipt("dispatch-planning"),
    ]


def test_clean_cross_consumer_adoption_requires_human_approval():
    svc = ReintegrationBaselineAdoptionConsistencyService()
    rec = svc.create(record_id="r1", workspace_id="ws-1", active_rollout=rollout(), receipts=clean_receipts(), source_key="s1")
    assert rec.status == "review-required"
    assert rec.consistency_score == 1.0
    with pytest.raises(ValueError):
        svc.approve("r1", human_approved=False)
    assert svc.approve("r1", human_approved=True).status == "consistent"


def test_version_drift_is_inconsistent():
    svc = ReintegrationBaselineAdoptionConsistencyService()
    receipts = clean_receipts()
    receipts[1] = receipt("worker-selection", baseline_version=2)
    rec = svc.create(record_id="r2", workspace_id="ws-1", active_rollout=rollout(), receipts=receipts, source_key="s2")
    assert rec.status == "inconsistent"
    assert "worker-selection" in rec.mismatched_consumers


def test_missing_receipt_fails_closed():
    svc = ReintegrationBaselineAdoptionConsistencyService()
    rec = svc.create(record_id="r3", workspace_id="ws-1", active_rollout=rollout(), receipts=clean_receipts()[:2], source_key="s3")
    assert rec.status == "inconsistent"
    assert rec.missing_consumers == ["dispatch-planning"]


def test_duplicate_consumer_receipts_fail_closed():
    svc = ReintegrationBaselineAdoptionConsistencyService()
    receipts = clean_receipts() + [receipt("adapter-selection", receipt_id="duplicate")]
    rec = svc.create(record_id="r4", workspace_id="ws-1", active_rollout=rollout(), receipts=receipts, source_key="s4")
    assert rec.status == "inconsistent"
    assert "adapter-selection" in rec.duplicate_consumers


def test_invalid_admission_and_risk_brain_block():
    svc = ReintegrationBaselineAdoptionConsistencyService()
    rec = svc.create(record_id="r5", workspace_id="ws-1", active_rollout=rollout(status="staged", risk_brain_blocked=True), receipts=clean_receipts(), source_key="s5")
    assert rec.status == "inconsistent"
    assert rec.risk_brain_blocked
    assert "rollout-not-active" in rec.findings


def test_replay_and_workspace_isolation():
    svc = ReintegrationBaselineAdoptionConsistencyService()
    svc.create(record_id="r6", workspace_id="ws-1", active_rollout=rollout(), receipts=clean_receipts(), source_key="same")
    with pytest.raises(ValueError):
        svc.create(record_id="r7", workspace_id="ws-1", active_rollout=rollout(), receipts=clean_receipts(), source_key="same")
    rec = svc.create(record_id="r8", workspace_id="ws-2", active_rollout=rollout(), receipts=clean_receipts(), source_key="same")
    assert rec.status == "inconsistent"
    assert "workspace-mismatch" in rec.findings


def test_unsupported_consumer_receipt_fails_closed():
    svc = ReintegrationBaselineAdoptionConsistencyService()
    receipts = clean_receipts() + [receipt("unknown-consumer")]
    rec = svc.create(record_id="r9", workspace_id="ws-1", active_rollout=rollout(), receipts=receipts, source_key="s9")
    assert rec.status == "inconsistent"
    assert "unsupported-consumer-receipt" in rec.findings
