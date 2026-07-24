import pytest

from app.schemas.agent_learning_adaptation import AgentLearningCreate
from app.services.agent_learning_adaptation import AgentLearningAdaptationService


def _payload(**overrides):
    observation = {
        "agent_id": "research-agent-1",
        "adaptation_id": "adapt-001",
        "adaptation_type": "policy-tuning-proposal",
        "evidence_quality": 0.95,
        "outcome_support": 0.95,
        "causal_confidence": 0.90,
        "generalization_score": 0.92,
        "safety_validation_score": 0.97,
        "regression_test_coverage": 0.95,
        "rollback_readiness": 0.98,
        "human_review_coverage": 1.0,
        "provenance_coverage": 1.0,
        "confidence": 0.95,
        "freshness": 1.0,
        "failed_regressions": 0,
        "safety_failures": 0,
        "rollback_failures": 0,
        "overfit_indicators": 0,
        "business_criticality": 0.60,
    }
    observation.update(overrides.pop("observation", {}))
    payload = {
        "workspace_id": "workspace-a",
        "source_key": "learning-001",
        "requested_by": "risk-owner",
        "observations": [observation],
    }
    payload.update(overrides)
    return AgentLearningCreate(**payload)


def test_status_is_governance_only():
    service = AgentLearningAdaptationService()
    status = service.status()
    assert status["version"] == "21.94"
    assert status["automatic_learning_enabled"] is False
    assert status["model_mutation_enabled"] is False
    assert status["agent_execution_enabled"] is False
    assert status["execution_enabled"] is False
    assert status["risk_brain_authoritative"] is True


def test_healthy_adaptation_can_be_approved_and_activated():
    service = AgentLearningAdaptationService()
    record = service.create(_payload())
    assert record.risk_flags == []
    service.act("workspace-a", record.record_id, "assess", "owner", "op-1")
    service.act("workspace-a", record.record_id, "submit-review", "owner", "op-2")
    approved = service.act("workspace-a", record.record_id, "approve", "human", "op-3")
    assert approved.approved_by == "human"
    active = service.act("workspace-a", record.record_id, "activate", "human", "op-4")
    assert active.state.value == "active"


def test_overfit_indicator_blocks_approval():
    service = AgentLearningAdaptationService()
    record = service.create(_payload(observation={"overfit_indicators": 1}))
    assert any(flag.startswith("overfit-alert:") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("workspace-a", record.record_id, "approve", "owner", "op-a")


def test_safety_failure_on_critical_agent_hard_blocks():
    service = AgentLearningAdaptationService()
    record = service.create(_payload(observation={"business_criticality": 0.95, "safety_failures": 1}))
    assert record.state.value == "blocked"
    assert "risk-brain-hard-block" in record.risk_flags


def test_regression_and_rollback_failures_are_flagged():
    service = AgentLearningAdaptationService()
    record = service.create(_payload(observation={"failed_regressions": 1, "rollback_failures": 1}))
    assert any(flag.startswith("regression-alert:") for flag in record.risk_flags)
    assert any(flag.startswith("rollback-alert:") for flag in record.risk_flags)


def test_operation_replay_is_rejected():
    service = AgentLearningAdaptationService()
    record = service.create(_payload())
    service.act("workspace-a", record.record_id, "assess", "owner", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("workspace-a", record.record_id, "monitor", "owner", "same-op")


def test_workspace_isolation():
    service = AgentLearningAdaptationService()
    record = service.create(_payload())
    with pytest.raises(KeyError):
        service.get("workspace-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = AgentLearningAdaptationService()
    service.create(_payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(_payload())
