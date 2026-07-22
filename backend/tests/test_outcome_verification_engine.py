import pytest

from app.modules.outcome_verification_engine.models import (
    OutcomeMetricInput,
    OutcomeVerificationCreate,
    VerificationAction,
    VerificationCommand,
    VerificationState,
)
from app.modules.outcome_verification_engine.service import OutcomeVerificationError, OutcomeVerificationService


def payload(**overrides):
    data = dict(
        workspace_id="ws-1",
        source_key="delivery-1",
        workflow_id="wf-1",
        execution_supervisor_record_id="sup-1",
        v21_11_evidence={"status": "completed"},
        workflow_completed=True,
        expected_benefit=1000,
        realized_benefit=950,
        total_cost=900,
        planned_cost=1000,
        metrics=[
            OutcomeMetricInput(
                key="quality",
                description="Delivered quality score",
                target_value=90,
                actual_value=92,
                tolerance_percent=5,
                weight=2,
                evidence_refs=["artifact://quality-report"],
            ),
            OutcomeMetricInput(
                key="latency",
                description="Delivery latency",
                target_value=10,
                actual_value=9,
                higher_is_better=False,
                evidence_refs=["metric://latency"],
            ),
        ],
    )
    data.update(overrides)
    return OutcomeVerificationCreate(**data)


def test_verifies_completed_outcomes():
    service = OutcomeVerificationService()
    record = service.create(payload())
    assert record.state == VerificationState.VERIFIED
    assert record.outcome_score >= 80
    assert record.evidence_coverage_score == 100
    assert not record.mandatory_failures


def test_risk_brain_block_is_authoritative():
    service = OutcomeVerificationService()
    record = service.create(payload(risk_brain_hard_block=True))
    assert record.state == VerificationState.BLOCKED
    assert not record.metric_results


def test_requires_v21_11_evidence_and_completion():
    service = OutcomeVerificationService()
    missing = service.create(payload(source_key="missing", v21_11_evidence={}))
    incomplete = service.create(payload(source_key="incomplete", workflow_completed=False))
    assert missing.state == VerificationState.EVIDENCE_REQUIRED
    assert incomplete.state == VerificationState.BLOCKED


def test_mandatory_failure_requires_human_review():
    service = OutcomeVerificationService()
    record = service.create(
        payload(
            metrics=[
                OutcomeMetricInput(
                    key="quality",
                    description="Quality",
                    target_value=90,
                    actual_value=60,
                    evidence_refs=["artifact://report"],
                )
            ]
        )
    )
    assert record.state == VerificationState.HUMAN_REVIEW_REQUIRED
    assert record.mandatory_failures == ["quality"]


def test_low_benefit_is_flagged_at_risk():
    service = OutcomeVerificationService()
    record = service.create(payload(realized_benefit=300))
    assert record.state == VerificationState.BENEFIT_AT_RISK


def test_acceptance_and_receipt_replay_protection():
    service = OutcomeVerificationService()
    first = service.create(payload(source_key="first"))
    second = service.create(payload(source_key="second"))

    service.execute(
        "ws-1",
        first.id,
        VerificationAction(command=VerificationCommand.ACCEPT, actor="owner", acceptance_token="accept-1"),
    )
    with pytest.raises(OutcomeVerificationError, match="replay"):
        service.execute(
            "ws-1",
            second.id,
            VerificationAction(command=VerificationCommand.ACCEPT, actor="owner", acceptance_token="accept-1"),
        )

    service.execute(
        "ws-1",
        first.id,
        VerificationAction(command=VerificationCommand.ISSUE, actor="owner", downstream_receipt="receipt-1"),
    )
    service.execute(
        "ws-1",
        second.id,
        VerificationAction(command=VerificationCommand.ACCEPT, actor="owner", acceptance_token="accept-2"),
    )
    with pytest.raises(OutcomeVerificationError, match="replay"):
        service.execute(
            "ws-1",
            second.id,
            VerificationAction(command=VerificationCommand.ISSUE, actor="owner", downstream_receipt="receipt-1"),
        )


def test_duplicate_and_workspace_isolation():
    service = OutcomeVerificationService()
    record = service.create(payload())
    with pytest.raises(OutcomeVerificationError, match="duplicate"):
        service.create(payload())
    with pytest.raises(OutcomeVerificationError, match="not found"):
        service.get("ws-2", record.id)
    assert len(service.audit("ws-1")) == 2
    assert service.audit("ws-2") == []
