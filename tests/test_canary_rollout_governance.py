import pytest

from app.modules.canary_rollout_governance.models import (
    CanaryMetric,
    RolloutAction,
    RolloutCreate,
    RolloutStage,
    RolloutState,
)
from app.modules.canary_rollout_governance.service import CanaryRolloutError, CanaryRolloutService


def payload(**overrides):
    values = {
        "workspace_id": "ws-1",
        "source_key": "rollout-1",
        "reliability_record_id": "reliability-1",
        "proposal_ids": ["proposal-1"],
        "target_runtime_ids": ["runtime-1"],
        "config_version": "config-v2",
        "rollback_version": "config-v1",
        "stages": [
            RolloutStage(stage_id="stage-10", traffic_percent=10, minimum_observations=2),
            RolloutStage(stage_id="stage-100", traffic_percent=100, minimum_observations=1),
        ],
        "metrics": [
            CanaryMetric(
                metric_id="error-rate",
                name="Execution error rate",
                baseline_value=0.01,
                failure_threshold=0.05,
                direction="max",
            ),
            CanaryMetric(
                metric_id="success-rate",
                name="Execution success rate",
                baseline_value=0.99,
                failure_threshold=0.95,
                direction="min",
            ),
        ],
        "upstream_evidence_verified": True,
    }
    values.update(overrides)
    return RolloutCreate(**values)


def approve_and_start(service: CanaryRolloutService, record_id: str) -> None:
    service.act(record_id, "ws-1", RolloutAction(action="approve", actor_id="operator", approval_token="approval-1"))
    service.act(record_id, "ws-1", RolloutAction(action="start-canary", actor_id="operator", receipt_id="start-1"))


def test_full_canary_promotion_lifecycle():
    service = CanaryRolloutService()
    record = service.create(payload())
    assert record.state == RolloutState.HUMAN_REVIEW_REQUIRED
    approve_and_start(service, record.record_id)

    record = service.act(
        record.record_id,
        "ws-1",
        RolloutAction(
            action="observe",
            actor_id="monitor",
            receipt_id="observe-1",
            observations={"error-rate": 0.02, "success-rate": 0.98},
            observation_count=2,
        ),
    )
    assert record.state == RolloutState.CANARY_RUNNING
    record = service.act(record.record_id, "ws-1", RolloutAction(action="advance-stage", actor_id="operator", receipt_id="advance-1"))
    assert record.current_stage_index == 1

    service.act(
        record.record_id,
        "ws-1",
        RolloutAction(
            action="observe",
            actor_id="monitor",
            receipt_id="observe-2",
            observations={"error-rate": 0.01, "success-rate": 0.99},
        ),
    )
    record = service.act(record.record_id, "ws-1", RolloutAction(action="advance-stage", actor_id="operator", receipt_id="advance-2"))
    assert record.state == RolloutState.PROMOTION_READY
    record = service.act(record.record_id, "ws-1", RolloutAction(action="promote", actor_id="operator", receipt_id="promote-1"))
    assert record.state == RolloutState.PROMOTED


def test_threshold_breach_pauses_and_allows_rollback():
    service = CanaryRolloutService()
    record = service.create(payload())
    approve_and_start(service, record.record_id)
    record = service.act(
        record.record_id,
        "ws-1",
        RolloutAction(
            action="observe",
            actor_id="monitor",
            receipt_id="observe-breach",
            observations={"error-rate": 0.08, "success-rate": 0.90},
        ),
    )
    assert record.state == RolloutState.PAUSED
    record = service.act(record.record_id, "ws-1", RolloutAction(action="rollback", actor_id="operator", receipt_id="rollback-1"))
    assert record.state == RolloutState.ROLLED_BACK


def test_hard_gates_replay_and_workspace_isolation():
    service = CanaryRolloutService()
    assert service.create(payload(source_key="blocked", risk_brain_blocked=True)).state == RolloutState.BLOCKED
    assert service.create(payload(source_key="missing", upstream_evidence_verified=False)).state == RolloutState.EVIDENCE_REQUIRED

    record = service.create(payload())
    approve_and_start(service, record.record_id)
    with pytest.raises(CanaryRolloutError, match="replay"):
        service.act(record.record_id, "ws-1", RolloutAction(action="pause", actor_id="operator", receipt_id="start-1"))
    with pytest.raises(CanaryRolloutError, match="not found"):
        service.get(record.record_id, "ws-2")


def test_minimum_observations_and_observation_integrity():
    service = CanaryRolloutService()
    record = service.create(payload())
    approve_and_start(service, record.record_id)
    with pytest.raises(CanaryRolloutError, match="every canary metric"):
        service.act(
            record.record_id,
            "ws-1",
            RolloutAction(
                action="observe",
                actor_id="monitor",
                receipt_id="partial",
                observations={"error-rate": 0.01},
            ),
        )
    with pytest.raises(CanaryRolloutError, match="minimum observations"):
        service.act(record.record_id, "ws-1", RolloutAction(action="advance-stage", actor_id="operator", receipt_id="advance-too-soon"))


def test_duplicate_and_invalid_rollout_inputs_rejected():
    service = CanaryRolloutService()
    service.create(payload())
    with pytest.raises(CanaryRolloutError, match="duplicate source"):
        service.create(payload())
    with pytest.raises(ValueError, match="duplicate rollout stage"):
        payload(
            source_key="duplicate-stage",
            stages=[
                RolloutStage(stage_id="x", traffic_percent=10, minimum_observations=1),
                RolloutStage(stage_id="x", traffic_percent=100, minimum_observations=1),
            ],
        )
    with pytest.raises(ValueError, match="final rollout stage"):
        payload(
            source_key="no-full-stage",
            stages=[RolloutStage(stage_id="x", traffic_percent=50, minimum_observations=1)],
        )
