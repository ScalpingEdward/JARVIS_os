import pytest

from app.executive_planning_receipt_reconciliation.models import (
    HandoffEvidence,
    PlanningReceiptCreate,
    PlanningReceiptEvidence,
    PlanningReceiptExecuteRequest,
    PlanningReceiptState,
)
from app.executive_planning_receipt_reconciliation.service import PlanningReceiptReconciliationService


def build_payload(workspace_id: str = "ws-1", source_key: str = "source-1") -> PlanningReceiptCreate:
    handoff = HandoffEvidence(
        handoff_record_id="handoff-1",
        handoff_state="accepted-by-v20.01",
        handoff_token="handoff-token-123",
        evidence_digest="digest-12345678",
        objective="Improve runtime resilience",
        scope=["broker reconnect", "health verification"],
        acceptance_criteria=["reconnect is bounded", "health is verified"],
        constraints=["defensive only", "no risk increase"],
        dependencies=["v20.07 telemetry"],
        priority_score=92,
        confidence_score=88,
        effort_points=5,
        human_approved=True,
    )
    receipt = PlanningReceiptEvidence(
        receipt_id="receipt-1",
        target_module="v20.01",
        handoff_token=handoff.handoff_token,
        evidence_digest=handoff.evidence_digest,
        objective=handoff.objective,
        scope=list(reversed(handoff.scope)),
        acceptance_criteria=list(handoff.acceptance_criteria),
        constraints=list(handoff.constraints),
        dependencies=list(handoff.dependencies),
        priority_score=handoff.priority_score,
        confidence_score=handoff.confidence_score,
        effort_points=handoff.effort_points,
        accepted=True,
    )
    return PlanningReceiptCreate(
        workspace_id=workspace_id,
        source_key=source_key,
        actor_id="tester",
        v20_10_accepted=True,
        handoff=handoff,
        receipt=receipt,
    )


def test_reconciles_matching_receipt_and_confirms_continuity():
    service = PlanningReceiptReconciliationService()
    record = service.create(build_payload())

    assert record.state == PlanningReceiptState.RECONCILED
    assert record.findings == []
    assert record.continuity_token

    confirmed = service.execute(
        record.id,
        "ws-1",
        PlanningReceiptExecuteRequest(action="confirm-continuity", actor_id="reviewer", human_approved=True),
    )
    assert confirmed.state == PlanningReceiptState.CONTINUITY_CONFIRMED


def test_detects_critical_digest_drift():
    service = PlanningReceiptReconciliationService()
    payload = build_payload()
    payload.receipt.evidence_digest = "changed-digest"

    record = service.create(payload)

    assert record.state == PlanningReceiptState.DRIFT_DETECTED
    assert any(item.field == "evidence_digest" and item.severity == "critical" for item in record.findings)


def test_drift_requires_review_before_any_continuity_confirmation():
    service = PlanningReceiptReconciliationService()
    payload = build_payload()
    payload.receipt.constraints = ["defensive only"]
    record = service.create(payload)

    with pytest.raises(ValueError, match="continuity confirmation unavailable"):
        service.execute(
            record.id,
            "ws-1",
            PlanningReceiptExecuteRequest(action="confirm-continuity", actor_id="reviewer", human_approved=True),
        )

    reviewed = service.execute(
        record.id,
        "ws-1",
        PlanningReceiptExecuteRequest(action="request-review", actor_id="reviewer"),
    )
    assert reviewed.state == PlanningReceiptState.HUMAN_REVIEW_REQUIRED


def test_missing_v20_10_evidence_fails_closed():
    service = PlanningReceiptReconciliationService()
    payload = build_payload()
    payload.v20_10_accepted = False

    record = service.create(payload)
    assert record.state == PlanningReceiptState.EVIDENCE_REQUIRED


def test_risk_brain_block_is_absolute():
    service = PlanningReceiptReconciliationService()
    payload = build_payload()
    payload.upstream_risk_brain_blocked = True

    record = service.create(payload)
    assert record.state == PlanningReceiptState.BLOCKED


def test_wrong_target_module_is_blocked():
    service = PlanningReceiptReconciliationService()
    payload = build_payload()
    payload.receipt.target_module = "v20.02"

    record = service.create(payload)
    assert record.state == PlanningReceiptState.BLOCKED


def test_human_approval_is_required_for_continuity():
    service = PlanningReceiptReconciliationService()
    record = service.create(build_payload())

    with pytest.raises(ValueError, match="human approval required"):
        service.execute(
            record.id,
            "ws-1",
            PlanningReceiptExecuteRequest(action="confirm-continuity", actor_id="reviewer"),
        )


def test_duplicate_source_key_is_rejected():
    service = PlanningReceiptReconciliationService()
    service.create(build_payload())

    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(build_payload())


def test_workspace_isolation():
    service = PlanningReceiptReconciliationService()
    record = service.create(build_payload())

    assert service.get(record.id, "other-workspace") is None
    assert service.list_records("other-workspace") == []
    assert service.audit_records("other-workspace") == []
