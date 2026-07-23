import pytest

from backend.app.modules.operational_learning.models import (
    LearningActionRequest,
    LearningCreate,
    LearningRecommendation,
    LearningState,
    OutcomeStatus,
    RecommendationType,
    RecoveryOutcome,
    RiskDecision,
)
from backend.app.modules.operational_learning.service import OperationalLearningError, OperationalLearningService


def payload(workspace_id: str = "ws-1", source_key: str = "source-1") -> LearningCreate:
    outcomes = [
        RecoveryOutcome(
            outcome_id=f"outcome-{index}",
            supervisor_id=f"supervisor-{index}",
            orchestration_id=f"orchestration-{index}",
            status=OutcomeStatus.HEALTHY if index < 2 else OutcomeStatus.FAILED,
            recovery_attempts=index + 1,
            time_to_recovery_seconds=30 + index,
            healthy_cycles=3,
            trigger_fingerprint="latency-spike",
            evidence_refs=[f"evidence-{index}"],
        )
        for index in range(3)
    ]
    recommendations = [
        LearningRecommendation(
            recommendation_id="rec-1",
            recommendation_type=RecommendationType.STABILIZATION,
            target="self-healing-supervisor.required_healthy_cycles",
            rationale="Observed recoveries stabilize reliably after four healthy cycles.",
            baseline_value=3,
            proposed_value=4,
            confidence=0.9,
            expected_impact="Reduce premature recovery completion.",
            rollback_condition="Recovery duration increases above policy threshold.",
            evidence_refs=["analysis-1"],
        )
    ]
    return LearningCreate(
        workspace_id=workspace_id,
        source_key=source_key,
        target_system="phoenix-runtime",
        outcomes=outcomes,
        recommendations=recommendations,
        minimum_sample_size=3,
        minimum_confidence=0.8,
        validation_cycles_required=2,
        learning_evidence_refs=["learning-1"],
    )


def action(name: str, **kwargs) -> LearningActionRequest:
    return LearningActionRequest(action=name, actor="operator", **kwargs)


def test_full_learning_lifecycle() -> None:
    service = OperationalLearningService()
    record = service.create(payload())
    record = service.act(record.record_id, "ws-1", action("prepare-evidence"))
    assert record.state == LearningState.EVIDENCE_READY
    record = service.act(record.record_id, "ws-1", action("analyze"))
    record = service.act(record.record_id, "ws-1", action("propose", recommendation_ids=["rec-1"]))
    record = service.act(record.record_id, "ws-1", action("request-review"))
    record = service.act(record.record_id, "ws-1", action("approve", approval_token="approval-1"))
    record = service.act(record.record_id, "ws-1", action("apply", receipt_id="apply-1"))
    record = service.act(
        record.record_id,
        "ws-1",
        action("record-validation", receipt_id="validation-1", validation_healthy=True, validation_evidence_refs=["v1"]),
    )
    record = service.act(
        record.record_id,
        "ws-1",
        action("record-validation", receipt_id="validation-2", validation_healthy=True, validation_evidence_refs=["v2"]),
    )
    record = service.act(record.record_id, "ws-1", action("verify"))
    assert record.state == LearningState.VERIFIED
    assert record.consecutive_healthy_cycles == 2


def test_confidence_gate_and_replay_protection() -> None:
    service = OperationalLearningService()
    data = payload()
    data.recommendations[0].confidence = 0.5
    record = service.create(data)
    service.act(record.record_id, "ws-1", action("prepare-evidence"))
    service.act(record.record_id, "ws-1", action("analyze"))
    with pytest.raises(OperationalLearningError, match="confidence"):
        service.act(record.record_id, "ws-1", action("propose", recommendation_ids=["rec-1"]))

    data = payload(source_key="source-2")
    record = service.create(data)
    service.act(record.record_id, "ws-1", action("prepare-evidence"))
    service.act(record.record_id, "ws-1", action("analyze"))
    service.act(record.record_id, "ws-1", action("propose", recommendation_ids=["rec-1"]))
    service.act(record.record_id, "ws-1", action("request-review"))
    service.act(record.record_id, "ws-1", action("approve", approval_token="shared-token"))

    other = service.create(payload(source_key="source-3"))
    service.act(other.record_id, "ws-1", action("prepare-evidence"))
    service.act(other.record_id, "ws-1", action("analyze"))
    service.act(other.record_id, "ws-1", action("propose", recommendation_ids=["rec-1"]))
    service.act(other.record_id, "ws-1", action("request-review"))
    with pytest.raises(OperationalLearningError, match="replay"):
        service.act(other.record_id, "ws-1", action("approve", approval_token="shared-token"))


def test_risk_block_sample_gate_and_workspace_isolation() -> None:
    service = OperationalLearningService()
    blocked_payload = payload()
    blocked_payload.risk_decision = RiskDecision.BLOCK
    blocked = service.create(blocked_payload)
    blocked = service.act(blocked.record_id, "ws-1", action("prepare-evidence"))
    assert blocked.state == LearningState.BLOCKED

    too_small = payload(source_key="small")
    too_small.minimum_sample_size = 4
    record = service.create(too_small)
    with pytest.raises(OperationalLearningError, match="sample size"):
        service.act(record.record_id, "ws-1", action("prepare-evidence"))

    with pytest.raises(OperationalLearningError, match="not found"):
        service.get(blocked.record_id, "ws-2")


def test_duplicate_source_key_and_validation_reset() -> None:
    service = OperationalLearningService()
    record = service.create(payload())
    with pytest.raises(OperationalLearningError, match="duplicate source key"):
        service.create(payload())

    for name, kwargs in [
        ("prepare-evidence", {}),
        ("analyze", {}),
        ("propose", {"recommendation_ids": ["rec-1"]}),
        ("request-review", {}),
        ("approve", {"approval_token": "a"}),
        ("apply", {"receipt_id": "r"}),
    ]:
        service.act(record.record_id, "ws-1", action(name, **kwargs))
    service.act(record.record_id, "ws-1", action("record-validation", receipt_id="v1", validation_healthy=True, validation_evidence_refs=["e1"]))
    record = service.act(record.record_id, "ws-1", action("record-validation", receipt_id="v2", validation_healthy=False, validation_evidence_refs=["e2"]))
    assert record.consecutive_healthy_cycles == 0
    with pytest.raises(OperationalLearningError, match="incomplete"):
        service.act(record.record_id, "ws-1", action("verify"))
