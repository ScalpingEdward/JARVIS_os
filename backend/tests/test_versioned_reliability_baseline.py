import pytest
from app.services.versioned_reliability_baseline import VersionedReliabilityBaselineService


def preview(**overrides):
    value = {
        "workspace_id": "ws-1",
        "status": "approved-preview",
        "human_approved": True,
        "risk_brain_blocked": False,
        "baseline_id": "rel-main",
        "baseline_version": 3,
        "baseline_value": 0.82,
        "candidate_version": 4,
        "candidate_value": 0.85,
    }
    value.update(overrides)
    return value


def test_clean_preview_can_be_committed_with_human_approval():
    svc = VersionedReliabilityBaselineService()
    rec = svc.create(record_id="r1", workspace_id="ws-1", approved_preview=preview(), source_key="s1")
    assert rec.status == "review-required"
    assert rec.rollback_version == 3
    assert rec.rollback_value == 0.82
    with pytest.raises(ValueError):
        svc.approve("r1", human_approved=False)
    assert svc.approve("r1", human_approved=True).status == "committed"


def test_version_regression_blocks():
    svc = VersionedReliabilityBaselineService()
    rec = svc.create(record_id="r2", workspace_id="ws-1", approved_preview=preview(candidate_version=3), source_key="s2")
    assert rec.status == "blocked"
    assert "candidate-version-regression" in rec.findings


def test_oversized_delta_blocks():
    svc = VersionedReliabilityBaselineService()
    rec = svc.create(record_id="r3", workspace_id="ws-1", approved_preview=preview(candidate_value=0.95), source_key="s3", max_delta=0.05)
    assert rec.status == "blocked"
    assert "candidate-delta-exceeds-limit" in rec.findings


def test_invalid_admission_and_risk_block_fail_closed():
    svc = VersionedReliabilityBaselineService()
    rec = svc.create(record_id="r4", workspace_id="ws-1", approved_preview=preview(status="review-required", human_approved=False, risk_brain_blocked=True), source_key="s4")
    assert rec.status == "blocked"
    assert rec.risk_brain_blocked


def test_replay_and_workspace_isolation():
    svc = VersionedReliabilityBaselineService()
    svc.create(record_id="r5", workspace_id="ws-1", approved_preview=preview(), source_key="same")
    with pytest.raises(ValueError):
        svc.create(record_id="r6", workspace_id="ws-1", approved_preview=preview(), source_key="same")
    rec = svc.create(record_id="r7", workspace_id="ws-2", approved_preview=preview(), source_key="same")
    assert rec.status == "blocked"
    assert "workspace-mismatch" in rec.findings
