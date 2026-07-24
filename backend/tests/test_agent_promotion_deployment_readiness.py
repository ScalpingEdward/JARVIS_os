import pytest

from app.schemas.agent_promotion_deployment_readiness import AgentPromotionCreate
from app.services.agent_promotion_deployment_readiness import AgentPromotionDeploymentReadinessService


def _payload(**overrides):
    observation = {
        "agent_id": "research-agent-1",
        "candidate_version": "2.1.0",
        "current_version": "2.0.0",
        "validation_coverage": 0.98,
        "regression_coverage": 0.97,
        "safety_validation_score": 0.96,
        "compatibility_score": 0.95,
        "dependency_readiness": 0.96,
        "observability_readiness": 0.95,
        "rollback_readiness": 0.98,
        "canary_readiness": 0.94,
        "change_traceability": 1.0,
        "human_review_coverage": 1.0,
        "confidence": 0.96,
        "freshness": 1.0,
        "blocking_findings": 0,
        "failed_regressions": 0,
        "rollback_failures": 0,
        "unresolved_dependencies": 0,
        "observability_gaps": 0,
        "business_criticality": 0.60,
    }
    observation.update(overrides.pop("observation", {}))
    payload = {
        "workspace_id": "workspace-a",
        "source_key": "promotion-001",
        "requested_by": "release-owner",
        "observations": [observation],
    }
    payload.update(overrides)
    return AgentPromotionCreate(**payload)


def test_status_is_advisory_only():
    service = AgentPromotionDeploymentReadinessService()
    status = service.status()
    assert status["version"] == "21.95"
    assert status["deployment_execution_enabled"] is False
    assert status["automatic_promotion_enabled"] is False
    assert status["traffic_shift_enabled"] is False
    assert status["automatic_rollback_enabled"] is False
    assert status["execution_enabled"] is False
    assert status["risk_brain_authoritative"] is True


def test_healthy_candidate_can_be_approved_and_activated():
    service = AgentPromotionDeploymentReadinessService()
    record = service.create(_payload())
    assert record.risk_flags == []
    service.act("workspace-a", record.record_id, "assess", "owner", "op-1")
    service.act("workspace-a", record.record_id, "submit-review", "owner", "op-2")
    approved = service.act("workspace-a", record.record_id, "approve", "human-approver", "op-3")
    assert approved.approved_by == "human-approver"
    active = service.act("workspace-a", record.record_id, "activate", "human-approver", "op-4")
    assert active.state.value == "active"


def test_failed_regression_blocks_approval():
    service = AgentPromotionDeploymentReadinessService()
    record = service.create(_payload(observation={"failed_regressions": 1}))
    assert any(flag.startswith("validation-gap:") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("workspace-a", record.record_id, "approve", "owner", "op-a")


def test_observability_gap_is_flagged():
    service = AgentPromotionDeploymentReadinessService()
    record = service.create(_payload(observation={"observability_gaps": 1}))
    assert any(flag.startswith("observability-alert:") for flag in record.risk_flags)


def test_critical_rollback_failure_hard_blocks():
    service = AgentPromotionDeploymentReadinessService()
    record = service.create(
        _payload(observation={"business_criticality": 0.95, "rollback_failures": 1})
    )
    assert record.state.value == "blocked"
    assert "risk-brain-hard-block" in record.risk_flags


def test_operation_replay_is_rejected():
    service = AgentPromotionDeploymentReadinessService()
    record = service.create(_payload())
    service.act("workspace-a", record.record_id, "assess", "owner", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("workspace-a", record.record_id, "monitor", "owner", "same-op")


def test_workspace_isolation():
    service = AgentPromotionDeploymentReadinessService()
    record = service.create(_payload())
    with pytest.raises(KeyError):
        service.get("workspace-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = AgentPromotionDeploymentReadinessService()
    service.create(_payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(_payload())
