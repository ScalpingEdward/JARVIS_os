import pytest

from app.modules.runtime_supervisor.models import HealthState, RuntimeAction, RuntimeCreate, RuntimeDependency, RuntimeState
from app.modules.runtime_supervisor.service import RuntimeSupervisorError, RuntimeSupervisorService


def payload(**overrides):
    values = {
        "workspace_id": "ws-1",
        "source_key": "runtime-1",
        "runtime_name": "primary-mt5-runtime",
        "broker_adapter": "mt5",
        "account_ref": "account-secret-ref",
        "active_policy_record_id": "policy-1",
        "workflow_record_id": "workflow-1",
        "command_record_ids": ["command-1"],
        "upstream_evidence_verified": True,
        "dependencies": [RuntimeDependency(name="broker-session", health=HealthState.HEALTHY)],
    }
    values.update(overrides)
    return RuntimeCreate(**values)


def test_approval_start_heartbeat_stop_and_archive():
    service = RuntimeSupervisorService()
    record = service.create(payload())
    assert record.state == RuntimeState.HUMAN_REVIEW_REQUIRED

    record = service.act(record.record_id, "ws-1", RuntimeAction(action="approve", actor_id="operator", approval_token="approval-1"))
    assert record.state == RuntimeState.APPROVED

    record = service.act(record.record_id, "ws-1", RuntimeAction(action="start", actor_id="operator", receipt_id="start-1"))
    assert record.state == RuntimeState.HEALTHY

    record = service.act(
        record.record_id,
        "ws-1",
        RuntimeAction(
            action="heartbeat",
            actor_id="supervisor",
            receipt_id="heartbeat-1",
            dependency_updates=[RuntimeDependency(name="broker-session", health=HealthState.DEGRADED)],
        ),
    )
    assert record.state == RuntimeState.DEGRADED

    record = service.act(record.record_id, "ws-1", RuntimeAction(action="stop", actor_id="operator", receipt_id="stop-1"))
    assert record.state == RuntimeState.STOPPED
    record = service.act(record.record_id, "ws-1", RuntimeAction(action="archive", actor_id="operator"))
    assert record.state == RuntimeState.ARCHIVED


def test_risk_brain_and_missing_evidence_are_hard_gates():
    service = RuntimeSupervisorService()
    assert service.create(payload(source_key="blocked", risk_brain_blocked=True)).state == RuntimeState.BLOCKED
    assert service.create(payload(source_key="missing", upstream_evidence_verified=False)).state == RuntimeState.EVIDENCE_REQUIRED


def test_replay_protection_and_workspace_isolation():
    service = RuntimeSupervisorService()
    record = service.create(payload())
    service.act(record.record_id, "ws-1", RuntimeAction(action="approve", actor_id="operator", approval_token="token"))

    second = service.create(payload(source_key="runtime-2"))
    with pytest.raises(RuntimeSupervisorError, match="replay"):
        service.act(second.record_id, "ws-1", RuntimeAction(action="approve", actor_id="operator", approval_token="token"))

    service.act(record.record_id, "ws-1", RuntimeAction(action="start", actor_id="operator", receipt_id="receipt"))
    with pytest.raises(RuntimeSupervisorError, match="replay"):
        service.act(record.record_id, "ws-1", RuntimeAction(action="heartbeat", actor_id="operator", receipt_id="receipt"))
    with pytest.raises(RuntimeSupervisorError, match="not found"):
        service.get(record.record_id, "ws-2")


def test_circuit_breaker_and_restart_limit():
    service = RuntimeSupervisorService()
    record = service.create(payload(max_consecutive_failures=2, restart_limit=1))
    service.act(record.record_id, "ws-1", RuntimeAction(action="approve", actor_id="operator", approval_token="approval"))
    service.act(record.record_id, "ws-1", RuntimeAction(action="start", actor_id="operator", receipt_id="start"))
    service.act(record.record_id, "ws-1", RuntimeAction(action="degrade", actor_id="monitor"))
    record = service.act(record.record_id, "ws-1", RuntimeAction(action="degrade", actor_id="monitor"))
    assert record.state == RuntimeState.CIRCUIT_OPEN

    record = service.act(record.record_id, "ws-1", RuntimeAction(action="restart", actor_id="operator", receipt_id="restart-1"))
    assert record.state == RuntimeState.STARTING
    service.act(record.record_id, "ws-1", RuntimeAction(action="fail", actor_id="monitor"))
    with pytest.raises(RuntimeSupervisorError, match="restart limit"):
        service.act(record.record_id, "ws-1", RuntimeAction(action="restart", actor_id="operator", receipt_id="restart-2"))


def test_duplicate_source_and_dependency_rejected():
    service = RuntimeSupervisorService()
    service.create(payload())
    with pytest.raises(RuntimeSupervisorError, match="duplicate source"):
        service.create(payload())
    with pytest.raises(ValueError, match="duplicate runtime dependency"):
        payload(source_key="dup-deps", dependencies=[RuntimeDependency(name="x"), RuntimeDependency(name="x")])
