from datetime import datetime, timedelta, timezone

import pytest

from app.modules.execution_supervisor.models import (
    StageTelemetry,
    SupervisionAction,
    SupervisionCommand,
    SupervisionCreate,
    SupervisionState,
)
from app.modules.execution_supervisor.service import ExecutionSupervisorError, ExecutionSupervisorService


def stage(key: str = "build", **overrides) -> StageTelemetry:
    data = {
        "stage_key": key,
        "status": "running",
        "progress_percent": 50,
        "elapsed_seconds": 50,
        "timeout_seconds": 100,
        "retry_count": 0,
        "retry_budget": 2,
        "error_rate": 0.01,
        "output_quality_score": 95,
        "dependency_healthy": True,
        "heartbeat_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return StageTelemetry(**data)


def payload(**overrides) -> SupervisionCreate:
    data = {
        "workspace_id": "ws-1",
        "source_key": "run-1",
        "workflow_id": "workflow-1",
        "workflow_approved": True,
        "v21_10_evidence": {"approval": "ok"},
        "stages": [stage()],
    }
    data.update(overrides)
    return SupervisionCreate(**data)


def test_healthy_workflow_is_observed() -> None:
    service = ExecutionSupervisorService()
    record = service.create(payload())
    assert record.state == SupervisionState.HEALTHY
    assert record.health_score >= 80
    assert record.incidents == []


def test_missing_evidence_is_blocked_from_observation() -> None:
    service = ExecutionSupervisorService()
    record = service.create(payload(v21_10_evidence={}))
    assert record.state == SupervisionState.EVIDENCE_REQUIRED


def test_risk_brain_hard_block_is_authoritative() -> None:
    service = ExecutionSupervisorService()
    record = service.create(payload(risk_brain_hard_block=True))
    assert record.state == SupervisionState.BLOCKED


def test_timeout_and_error_breach_create_incident() -> None:
    service = ExecutionSupervisorService()
    record = service.create(payload(stages=[stage(elapsed_seconds=120, error_rate=0.5)]))
    assert record.state == SupervisionState.INCIDENT
    assert {incident.code for incident in record.incidents} >= {"timeout-breach", "error-rate-breach"}


def test_stale_heartbeat_creates_critical_incident() -> None:
    service = ExecutionSupervisorService()
    stale = datetime.now(timezone.utc) - timedelta(hours=1)
    record = service.create(payload(stale_heartbeat_seconds=10, stages=[stage(heartbeat_at=stale)]))
    assert record.state == SupervisionState.INCIDENT
    assert any(incident.code == "stale-heartbeat" for incident in record.incidents)


def test_intervention_receipt_replay_is_rejected() -> None:
    service = ExecutionSupervisorService()
    first = service.create(payload(source_key="one", stages=[stage(error_rate=0.6)]))
    second = service.create(payload(source_key="two", workflow_id="workflow-2", stages=[stage("test", error_rate=0.6)]))
    action = SupervisionAction(
        command=SupervisionCommand.RECOMMEND_PAUSE,
        actor="operator",
        downstream_receipt="receipt-1",
    )
    service.execute("ws-1", first.id, action)
    with pytest.raises(ExecutionSupervisorError, match="replay"):
        service.execute("ws-1", second.id, action)


def test_duplicate_source_key_is_rejected() -> None:
    service = ExecutionSupervisorService()
    service.create(payload())
    with pytest.raises(ExecutionSupervisorError, match="duplicate"):
        service.create(payload())


def test_workspace_isolation() -> None:
    service = ExecutionSupervisorService()
    record = service.create(payload())
    with pytest.raises(ExecutionSupervisorError, match="not found"):
        service.get("other-workspace", record.id)


def test_completed_telemetry_finishes_record() -> None:
    service = ExecutionSupervisorService()
    record = service.create(payload(stages=[stage(status="completed", progress_percent=100)]))
    assert record.state == SupervisionState.COMPLETED
    assert record.completed_stages == 1
