import pytest

from app.schemas.agent_outcome_verification_feedback import AgentOutcomeVerificationCreate
from app.services.agent_outcome_verification_feedback import AgentOutcomeVerificationFeedbackService


def _payload(**overrides):
    observation = {
        "agent_id": "research-agent-1",
        "decision_id": "decision-001",
        "objective_id": "objective-001",
        "expected_outcome_score": 0.85,
        "observed_outcome_score": 0.83,
        "kpi_attainment_score": 0.92,
        "evidence_quality_score": 0.95,
        "feedback_coverage_score": 0.95,
        "causal_attribution_score": 0.90,
        "regression_detection_score": 0.95,
        "learning_traceability_score": 0.95,
        "rollback_readiness_score": 0.95,
        "human_review_coverage": 1.0,
        "confidence": 0.95,
        "freshness": 1.0,
        "adverse_outcomes": 0,
        "missed_kpis": 0,
        "repeated_regressions": 0,
        "unreviewed_feedback_items": 0,
        "business_criticality": 0.60,
    }
    observation.update(overrides.pop("observation", {}))
    payload = {
        "workspace_id": "workspace-a",
        "source_key": "outcome-001",
        "requested_by": "risk-owner",
        "observations": [observation],
    }
    payload.update(overrides)
    return AgentOutcomeVerificationCreate(**payload)


def test_status_is_advisory_only():
    service = AgentOutcomeVerificationFeedbackService()
    status = service.status()
    assert status["version"] == "21.93"
    assert status["feedback_mutation_enabled"] is False
    assert status["automatic_learning_enabled"] is False
    assert status["decision_mutation_enabled"] is False
    assert status["agent_execution_enabled"] is False
    assert status["execution_enabled"] is False
    assert status["risk_brain_authoritative"] is True


def test_healthy_outcome_can_be_approved_and_activated():
    service = AgentOutcomeVerificationFeedbackService()
    record = service.create(_payload())
    assert record.risk_flags == []
    service.act("workspace-a", record.record_id, "assess", "owner", "op-1")
    service.act("workspace-a", record.record_id, "submit-review", "owner", "op-2")
    approved = service.act("workspace-a", record.record_id, "approve", "human-approver", "op-3")
    assert approved.approved_by == "human-approver"
    active = service.act("workspace-a", record.record_id, "activate", "human-approver", "op-4")
    assert active.state.value == "active"


def test_outcome_drift_blocks_approval():
    service = AgentOutcomeVerificationFeedbackService()
    record = service.create(_payload(observation={"expected_outcome_score": 0.95, "observed_outcome_score": 0.40}))
    assert any(flag.startswith("outcome-drift:") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("workspace-a", record.record_id, "approve", "owner", "op-a")


def test_feedback_gap_is_flagged():
    service = AgentOutcomeVerificationFeedbackService()
    record = service.create(_payload(observation={"feedback_coverage_score": 0.50, "unreviewed_feedback_items": 3}))
    assert any(flag.startswith("feedback-gap:") for flag in record.risk_flags)
    assert record.dispositions[0].lifecycle_signal == "feedback-gap"


def test_critical_repeated_regression_hard_blocks():
    service = AgentOutcomeVerificationFeedbackService()
    record = service.create(
        _payload(observation={"business_criticality": 0.95, "repeated_regressions": 2})
    )
    assert record.state.value == "blocked"
    assert "risk-brain-hard-block" in record.risk_flags


def test_operation_replay_is_rejected():
    service = AgentOutcomeVerificationFeedbackService()
    record = service.create(_payload())
    service.act("workspace-a", record.record_id, "assess", "owner", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("workspace-a", record.record_id, "monitor", "owner", "same-op")


def test_workspace_isolation():
    service = AgentOutcomeVerificationFeedbackService()
    record = service.create(_payload())
    with pytest.raises(KeyError):
        service.get("workspace-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = AgentOutcomeVerificationFeedbackService()
    service.create(_payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(_payload())


def test_duplicate_agent_decision_pair_is_rejected():
    base = _payload().model_dump()
    base["source_key"] = "outcome-dup"
    base["observations"] = [base["observations"][0], base["observations"][0]]
    with pytest.raises(ValueError, match="duplicate agent/decision observation"):
        AgentOutcomeVerificationCreate(**base)
