import pytest

from app.schemas.execution_outcome_trust_feedback import OutcomeTrustAction, OutcomeTrustCreate
from app.services.execution_outcome_trust_feedback import ExecutionOutcomeTrustFeedbackService


def payload(**overrides):
    observation = {
        "attestation_record_id": "att-1",
        "attestation_digest": "attestation-digest",
        "adapter_id": "adapter-a",
        "worker_id": "worker-a",
        "policy_profile_id": "policy-a",
        "planner_context_id": "planner-a",
        "operation": "read-fetch",
        "target": "https://example.com/status",
        "attestation_state": "attested",
        "postconditions_passed": True,
        "no_prohibited_side_effects": True,
        "receipt_reconciled": True,
        "response_integrity": 0.98,
        "latency_quality": 0.95,
        "reliability_signal": 0.97,
        "evidence_confidence": 0.99,
        "freshness": 0.99,
        "criticality": 0.6,
    }
    observation.update(overrides)
    return OutcomeTrustCreate(
        workspace_id="ws-a",
        source_key="outcome-1",
        requested_by="operator",
        observations=[observation],
    )


def action(name, operation_id):
    return OutcomeTrustAction(workspace_id="ws-a", action=name, actor="owner", operation_id=operation_id)


def test_status_keeps_feedback_advisory_only():
    status = ExecutionOutcomeTrustFeedbackService().status()
    assert status["version"] == "21.132"
    assert status["learning_feedback_enabled"] is True
    assert status["autonomous_policy_mutation_enabled"] is False
    assert status["autonomous_weight_mutation_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_clean_attested_outcome_can_be_approved_and_activated():
    service = ExecutionOutcomeTrustFeedbackService()
    record = service.create(payload())
    assert not record.risk_flags
    assert record.feedback[0].feedback_signal == "positive-feedback"
    record = service.act(record.record_id, action("approve", "op-1"))
    assert record.approved_by == "owner"
    record = service.act(record.record_id, action("activate", "op-2"))
    assert record.state.value == "active"


def test_low_trust_generates_caution_feedback_and_blocks_approval():
    service = ExecutionOutcomeTrustFeedbackService()
    record = service.create(payload(response_integrity=0.2, reliability_signal=0.2, latency_quality=0.2))
    assert record.feedback[0].feedback_signal == "caution-feedback"
    assert any(flag.startswith("low-trust") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act(record.record_id, action("approve", "op-low"))


def test_prohibited_side_effect_hard_blocks():
    service = ExecutionOutcomeTrustFeedbackService()
    record = service.create(payload(no_prohibited_side_effects=False, criticality=0.95))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_protected_operation_hard_blocks_even_with_good_metrics():
    service = ExecutionOutcomeTrustFeedbackService()
    record = service.create(payload(operation="trade-execute"))
    assert "risk-brain-hard-block" in record.risk_flags


def test_replay_workspace_isolation_and_duplicate_source():
    service = ExecutionOutcomeTrustFeedbackService()
    record = service.create(payload())
    service.act(record.record_id, action("score", "same-op"))
    with pytest.raises(ValueError, match="replay"):
        service.act(record.record_id, action("submit-review", "same-op"))
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
