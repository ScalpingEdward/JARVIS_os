import pytest

from app.modules.reliability_control_plane.models import (
    ControlMetric,
    OptimizationProposal,
    ReliabilityAction,
    ReliabilityBand,
    ReliabilityCreate,
    ReliabilityState,
)
from app.modules.reliability_control_plane.service import ReliabilityControlPlaneError, ReliabilityControlPlaneService


def payload(**overrides):
    values = {
        "workspace_id": "ws-1",
        "source_key": "assessment-1",
        "review_record_id": "review-1",
        "system_name": "primary-trading-control-plane",
        "upstream_evidence_verified": True,
        "metrics": [
            ControlMetric(metric_id="availability", name="Availability", weight=0.5, observed_value=99.0, target_value=99.9),
            ControlMetric(metric_id="recovery", name="Recovery time", weight=0.5, observed_value=8, target_value=10, higher_is_better=False),
        ],
        "proposals": [
            OptimizationProposal(
                proposal_id="p-1",
                control_name="heartbeat-timeout",
                current_value="30",
                proposed_value="20",
                expected_impact="faster fault detection",
            )
        ],
    }
    values.update(overrides)
    return ReliabilityCreate(**values)


def test_full_scoring_approval_optimization_and_verification_lifecycle():
    service = ReliabilityControlPlaneService()
    record = service.create(payload())
    assert record.state == ReliabilityState.DRAFT

    record = service.act(record.record_id, "ws-1", ReliabilityAction(action="score", actor_id="system"))
    assert record.state == ReliabilityState.SCORED
    assert record.score > 80
    assert record.band in {ReliabilityBand.STRONG, ReliabilityBand.EXCELLENT}

    service.act(record.record_id, "ws-1", ReliabilityAction(action="request-review", actor_id="system"))
    service.act(record.record_id, "ws-1", ReliabilityAction(action="approve", actor_id="operator", approval_token="approval-123"))
    service.act(record.record_id, "ws-1", ReliabilityAction(action="queue-optimization", actor_id="operator", receipt_id="queue-1"))
    record = service.act(
        record.record_id,
        "ws-1",
        ReliabilityAction(action="apply", actor_id="runtime", receipt_id="apply-1", applied_proposal_ids=["p-1"]),
    )
    assert record.state == ReliabilityState.APPLIED
    record = service.act(
        record.record_id,
        "ws-1",
        ReliabilityAction(action="verify", actor_id="auditor", receipt_id="verify-1", verification_passed=True),
    )
    assert record.state == ReliabilityState.VERIFIED
    assert service.act(record.record_id, "ws-1", ReliabilityAction(action="archive", actor_id="auditor")).state == ReliabilityState.ARCHIVED


def test_hard_gates_replay_and_workspace_isolation():
    service = ReliabilityControlPlaneService()
    assert service.create(payload(source_key="blocked", risk_brain_blocked=True)).state == ReliabilityState.BLOCKED
    assert service.create(payload(source_key="missing", upstream_evidence_verified=False)).state == ReliabilityState.EVIDENCE_REQUIRED

    first = service.create(payload())
    service.act(first.record_id, "ws-1", ReliabilityAction(action="score", actor_id="system"))
    service.act(first.record_id, "ws-1", ReliabilityAction(action="request-review", actor_id="system"))
    service.act(first.record_id, "ws-1", ReliabilityAction(action="approve", actor_id="operator", approval_token="same-token"))

    second = service.create(payload(source_key="assessment-2"))
    service.act(second.record_id, "ws-1", ReliabilityAction(action="score", actor_id="system"))
    service.act(second.record_id, "ws-1", ReliabilityAction(action="request-review", actor_id="system"))
    with pytest.raises(ReliabilityControlPlaneError, match="replay"):
        service.act(second.record_id, "ws-1", ReliabilityAction(action="approve", actor_id="operator", approval_token="same-token"))
    with pytest.raises(ReliabilityControlPlaneError, match="not found"):
        service.get(first.record_id, "ws-2")


def test_invalid_proposal_selection_and_verification_failure():
    service = ReliabilityControlPlaneService()
    record = service.create(payload())
    service.act(record.record_id, "ws-1", ReliabilityAction(action="score", actor_id="system"))
    service.act(record.record_id, "ws-1", ReliabilityAction(action="request-review", actor_id="system"))
    service.act(record.record_id, "ws-1", ReliabilityAction(action="approve", actor_id="operator", approval_token="approval-xyz"))
    service.act(record.record_id, "ws-1", ReliabilityAction(action="queue-optimization", actor_id="operator", receipt_id="queue"))
    with pytest.raises(ReliabilityControlPlaneError, match="unknown or empty"):
        service.act(record.record_id, "ws-1", ReliabilityAction(action="apply", actor_id="runtime", receipt_id="apply", applied_proposal_ids=["missing"]))


def test_duplicate_inputs_and_invalid_weights_rejected():
    service = ReliabilityControlPlaneService()
    service.create(payload())
    with pytest.raises(ReliabilityControlPlaneError, match="duplicate source"):
        service.create(payload())
    with pytest.raises(ValueError, match="duplicate reliability metric"):
        payload(source_key="dup-metric", metrics=[ControlMetric(metric_id="x", name="x", weight=0.5, observed_value=1, target_value=1), ControlMetric(metric_id="x", name="x2", weight=0.5, observed_value=1, target_value=1)])
    with pytest.raises(ValueError, match="weights"):
        payload(source_key="bad-weight", metrics=[ControlMetric(metric_id="x", name="x", weight=0.8, observed_value=1, target_value=1)])
