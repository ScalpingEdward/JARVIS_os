import pytest

from app.schemas.exchange_infrastructure_health import (
    InfrastructureHealthAction,
    InfrastructureHealthCreate,
    InfrastructureObservation,
)
from app.services.exchange_infrastructure_health import ExchangeInfrastructureHealthService


def payload(workspace_id: str = "ws-1", source_key: str = "infra-1") -> InfrastructureHealthCreate:
    return InfrastructureHealthCreate(
        workspace_id=workspace_id,
        source_key=source_key,
        requested_by="operator",
        observations=[
            InfrastructureObservation(
                venue_id="venue-a",
                region="eu-central",
                gateway_latency_ms=35,
                market_data_latency_ms=22,
                order_ack_latency_ms=41,
                packet_loss_rate=0.001,
                disconnect_rate=0.001,
                stale_quote_rate=0.002,
                uptime_rate=0.9998,
                cpu_utilization=0.35,
                memory_utilization=0.42,
                queue_utilization=0.30,
                error_rate=0.001,
                failover_readiness=0.95,
                time_sync_drift_ms=2,
            )
        ],
    )


def test_scores_infrastructure_health_and_preserves_safety_boundary() -> None:
    service = ExchangeInfrastructureHealthService()
    record = service.create(payload())
    assert record.scores.aggregate_health > 0.5
    assert record.assessments[0].operational_signal == "stable"
    status = service.status()
    assert status["infrastructure_mutation_enabled"] is False
    assert status["routing_mutation_enabled"] is False
    assert status["failover_execution_enabled"] is False
    assert status["execution_enabled"] is False


def test_detects_failover_required() -> None:
    service = ExchangeInfrastructureHealthService()
    p = payload()
    p.observations[0].failover_readiness = 0.2
    p.observations[0].gateway_latency_ms = 300
    record = service.create(p)
    assert "failover-required" in record.assessments[0].operational_signal
    assert any(flag.endswith("failover-required") for flag in record.risk_flags)


def test_requires_human_approval_before_activation() -> None:
    service = ExchangeInfrastructureHealthService()
    record = service.create(payload())
    with pytest.raises(PermissionError):
        service.act("ws-1", record.record_id, InfrastructureHealthAction(action="activate", actor="operator", operation_id="op-1"))
    approved = service.act("ws-1", record.record_id, InfrastructureHealthAction(action="approve", actor="reviewer", operation_id="op-2"))
    assert approved.approved_by == "reviewer"
    active = service.act("ws-1", record.record_id, InfrastructureHealthAction(action="activate", actor="operator", operation_id="op-3"))
    assert active.state.value == "active"


def test_replay_workspace_isolation_and_duplicate_source_protection() -> None:
    service = ExchangeInfrastructureHealthService()
    record = service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    with pytest.raises(KeyError):
        service.get("other-workspace", record.record_id)
    action = InfrastructureHealthAction(action="score", actor="operator", operation_id="same-op")
    service.act("ws-1", record.record_id, action)
    with pytest.raises(ValueError):
        service.act("ws-1", record.record_id, action)


def test_risk_brain_hard_block_is_authoritative() -> None:
    service = ExchangeInfrastructureHealthService()
    record = service.create(payload())
    service.set_risk_brain_block("ws-1", True)
    with pytest.raises(PermissionError):
        service.act("ws-1", record.record_id, InfrastructureHealthAction(action="approve", actor="reviewer", operation_id="op-blocked"))
