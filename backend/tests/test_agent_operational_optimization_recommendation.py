import pytest

from app.schemas.agent_operational_optimization_recommendation import OptimizationCreate
from app.services.agent_operational_optimization_recommendation import AgentOperationalOptimizationRecommendationService


def payload(**overrides):
    observation = {
        "agent_id": "phoenix-agent",
        "agent_version": "21.110",
        "recommendation_id": "opt-001",
        "performance_gain_confidence": 0.90,
        "cost_reduction_confidence": 0.85,
        "resource_efficiency_gain": 0.88,
        "reliability_impact": 0.98,
        "reversibility": 0.98,
        "validation_coverage": 0.98,
        "observability_readiness": 0.98,
        "rollback_readiness": 0.98,
        "dependency_impact_clarity": 0.98,
        "human_review_coverage": 1.0,
        "confidence": 1.0,
        "freshness": 1.0,
        "criticality": 0.70,
    }
    observation.update(overrides)
    return OptimizationCreate(
        workspace_id="ws-a",
        source_key="optimization-source",
        requested_by="operator",
        observations=[observation],
    )


def test_status_is_advisory_only():
    status = AgentOperationalOptimizationRecommendationService().status()
    assert status["version"] == "21.110"
    assert status["automatic_tuning_enabled"] is False
    assert status["autoscaling_enabled"] is False
    assert status["configuration_mutation_enabled"] is False
    assert status["deployment_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_clean_recommendation_can_be_approved_and_published():
    service = AgentOperationalOptimizationRecommendationService()
    record = service.create(payload())
    assert not record.risk_flags
    record = service.act("ws-a", record.record_id, "approve", "owner", "op-1")
    record = service.act("ws-a", record.record_id, "publish-advisory", "owner", "op-2")
    assert record.state.value == "advisory-ready"


def test_validation_findings_block_approval():
    service = AgentOperationalOptimizationRecommendationService()
    record = service.create(payload(validation_coverage=0.40, unresolved_validation_findings=1))
    assert any(flag.startswith("validation-alert") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "owner", "op-a")


def test_critical_unsafe_recommendation_hard_blocks():
    service = AgentOperationalOptimizationRecommendationService()
    record = service.create(payload(
        criticality=0.98,
        reversibility=0.10,
        rollback_readiness=0.10,
        rollback_failures=1,
        unresolved_validation_findings=2,
    ))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_replay_workspace_isolation_and_duplicate_source():
    service = AgentOperationalOptimizationRecommendationService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "assess", "reviewer", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "submit-review", "reviewer", "same-op")
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
