import pytest

from app.schemas.agent_resilience_capacity_stress import CapacityStressCreate
from app.services.agent_resilience_capacity_stress import AgentResilienceCapacityStressService


def payload(**overrides):
    observation = {
        "agent_id": "phoenix-agent", "agent_version": "21.102", "scenario_id": "peak-load",
        "load_headroom": 0.60, "concurrency_headroom": 0.60, "queue_headroom": 0.60,
        "latency_stability": 0.98, "error_stability": 0.98, "resource_efficiency": 0.95,
        "dependency_capacity": 0.60, "degradation_quality": 0.95, "recovery_readiness": 0.98,
        "observability_coverage": 0.98, "confidence": 1.0, "freshness": 1.0, "criticality": 0.70,
    }
    observation.update(overrides)
    return CapacityStressCreate(
        workspace_id="ws-a", source_key="capacity-source", requested_by="operator", observations=[observation]
    )


def test_status_disables_execution():
    status = AgentResilienceCapacityStressService().status()
    assert status["version"] == "21.102"
    assert status["stress_execution_enabled"] is False
    assert status["load_generation_enabled"] is False
    assert status["autoscaling_enabled"] is False
    assert status["agent_execution_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_healthy_capacity_record_can_be_approved():
    service = AgentResilienceCapacityStressService()
    record = service.create(payload())
    assert not record.risk_flags
    record = service.act("ws-a", record.record_id, "assess", "reviewer", "op-1")
    record = service.act("ws-a", record.record_id, "submit-review", "reviewer", "op-2")
    record = service.act("ws-a", record.record_id, "approve", "owner", "op-3")
    assert record.approved_by == "owner"


def test_saturation_findings_block_approval():
    service = AgentResilienceCapacityStressService()
    record = service.create(payload(saturation_events=1, latency_stability=0.50))
    assert any(flag.startswith("saturation-alert") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "owner", "op-a")


def test_critical_capacity_failure_hard_blocks():
    service = AgentResilienceCapacityStressService()
    record = service.create(payload(
        criticality=0.98, load_headroom=0.05, concurrency_headroom=0.05, queue_headroom=0.05,
        saturation_events=3, failed_recovery_checks=1, dependency_bottlenecks=2,
    ))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_operation_replay_rejected():
    service = AgentResilienceCapacityStressService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "assess", "reviewer", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "submit-review", "reviewer", "same-op")


def test_workspace_isolation():
    service = AgentResilienceCapacityStressService()
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_rejected():
    service = AgentResilienceCapacityStressService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
