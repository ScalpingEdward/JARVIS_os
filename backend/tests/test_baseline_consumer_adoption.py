import pytest
from app.services.baseline_consumer_adoption import BaselineConsumerAdoptionService


def rollout(**overrides):
    value = {
        "rollout_id": "r1",
        "workspace_id": "ws-1",
        "status": "active",
        "consumers": ["adapter-selection", "worker-selection"],
        "baseline_id": "b1",
        "baseline_version": 3,
        "baseline_digest": "digest-v3",
        "risk_brain_blocked": False,
    }
    value.update(overrides)
    return value


def test_exact_adoption_is_acknowledged():
    svc = BaselineConsumerAdoptionService()
    rec = svc.acknowledge(
        receipt_id="a1", workspace_id="ws-1", rollout=rollout(), consumer_id="consumer-a",
        consumer_type="adapter-selection", observed_baseline_id="b1", observed_baseline_version=3,
        observed_baseline_digest="digest-v3", source_key="s1",
    )
    assert rec.status == "adopted"
    assert not rec.drift_detected


def test_version_drift_is_detected_and_requires_review():
    svc = BaselineConsumerAdoptionService()
    rec = svc.acknowledge(
        receipt_id="a2", workspace_id="ws-1", rollout=rollout(), consumer_id="consumer-a",
        consumer_type="adapter-selection", observed_baseline_id="b1", observed_baseline_version=2,
        observed_baseline_digest="digest-v3", source_key="s2",
    )
    assert rec.status == "drift-detected"
    assert "baseline-version-drift" in rec.findings
    with pytest.raises(ValueError):
        svc.review_drift("a2", human_reviewed=False)
    assert svc.review_drift("a2", human_reviewed=True).status == "drift-reviewed"


def test_digest_drift_is_detected():
    svc = BaselineConsumerAdoptionService()
    rec = svc.acknowledge(
        receipt_id="a3", workspace_id="ws-1", rollout=rollout(), consumer_id="consumer-a",
        consumer_type="adapter-selection", observed_baseline_id="b1", observed_baseline_version=3,
        observed_baseline_digest="wrong", source_key="s3",
    )
    assert rec.drift_detected
    assert "baseline-digest-drift" in rec.findings


def test_consumer_must_be_supported_and_allow_listed():
    svc = BaselineConsumerAdoptionService()
    rec = svc.acknowledge(
        receipt_id="a4", workspace_id="ws-1", rollout=rollout(), consumer_id="consumer-x",
        consumer_type="unknown-consumer", observed_baseline_id="b1", observed_baseline_version=3,
        observed_baseline_digest="digest-v3", source_key="s4",
    )
    assert rec.status == "blocked"
    assert "unsupported-consumer" in rec.findings


def test_risk_brain_block_propagates():
    svc = BaselineConsumerAdoptionService()
    rec = svc.acknowledge(
        receipt_id="a5", workspace_id="ws-1", rollout=rollout(risk_brain_blocked=True), consumer_id="consumer-a",
        consumer_type="adapter-selection", observed_baseline_id="b1", observed_baseline_version=3,
        observed_baseline_digest="digest-v3", source_key="s5",
    )
    assert rec.status == "blocked"
    assert rec.risk_brain_blocked


def test_replay_and_workspace_isolation():
    svc = BaselineConsumerAdoptionService()
    svc.acknowledge(
        receipt_id="a6", workspace_id="ws-1", rollout=rollout(), consumer_id="consumer-a",
        consumer_type="adapter-selection", observed_baseline_id="b1", observed_baseline_version=3,
        observed_baseline_digest="digest-v3", source_key="same",
    )
    with pytest.raises(ValueError):
        svc.acknowledge(
            receipt_id="a7", workspace_id="ws-1", rollout=rollout(), consumer_id="consumer-b",
            consumer_type="worker-selection", observed_baseline_id="b1", observed_baseline_version=3,
            observed_baseline_digest="digest-v3", source_key="same",
        )
    rec = svc.acknowledge(
        receipt_id="a8", workspace_id="ws-2", rollout=rollout(), consumer_id="consumer-a",
        consumer_type="adapter-selection", observed_baseline_id="b1", observed_baseline_version=3,
        observed_baseline_digest="digest-v3", source_key="same",
    )
    assert rec.status == "blocked"
    assert "workspace-mismatch" in rec.findings
