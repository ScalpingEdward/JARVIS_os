import pytest

from app.modules.executive_work_order_readiness.models import (
    ContinuityEvidence,
    WorkOrderReadinessCreate,
    WorkOrderReadinessExecuteRequest,
    WorkOrderReadinessState,
)
from app.modules.executive_work_order_readiness.service import WorkOrderReadinessService


def payload(workspace: str = "alpha", **overrides):
    evidence = ContinuityEvidence(
        reconciliation_record_id="rec-1",
        reconciliation_state="continuity-confirmed",
        continuity_token="continuity-token-1",
        handoff_token="handoff-token-1",
        evidence_digest="digest-12345",
        objective="add defensive broker reconnect guard",
        scope=["broker adapter", "health monitor"],
        acceptance_criteria=["disconnect detected", "bounded reconnect verified"],
        constraints=["no risk increase", "no strategy changes"],
        dependencies=["broker-sandbox"],
        priority_score=85,
        confidence_score=90,
        effort_points=5,
        human_approved=True,
    )
    data = dict(
        workspace_id=workspace,
        source_key="source-1",
        actor_id="operator",
        v20_11_continuity_confirmed=True,
        upstream_risk_brain_blocked=False,
        evidence=evidence,
        dependency_status={"broker-sandbox": True},
    )
    data.update(overrides)
    return WorkOrderReadinessCreate(**data)


def test_work_order_requires_human_approval_then_issues_and_accepts():
    service = WorkOrderReadinessService()
    record = service.create(payload())
    assert record.state == WorkOrderReadinessState.HUMAN_REVIEW_REQUIRED
    assert record.work_order is not None

    record = service.execute(record.id, "alpha", WorkOrderReadinessExecuteRequest(
        action="approve-readiness", actor_id="owner", human_approved=True
    ))
    assert record.state == WorkOrderReadinessState.READY

    record = service.execute(record.id, "alpha", WorkOrderReadinessExecuteRequest(
        action="issue", actor_id="owner", human_approved=True
    ))
    assert record.state == WorkOrderReadinessState.ISSUED
    assert record.issuance_token

    record = service.execute(record.id, "alpha", WorkOrderReadinessExecuteRequest(
        action="accept", actor_id="engineering", engineering_receipt_id="eng-receipt-1"
    ))
    assert record.state == WorkOrderReadinessState.ACCEPTED_BY_ENGINEERING


def test_unresolved_dependency_blocks_readiness():
    service = WorkOrderReadinessService()
    record = service.create(payload(dependency_status={"broker-sandbox": False}))
    assert record.state == WorkOrderReadinessState.DEPENDENCY_BLOCKED


def test_missing_continuity_evidence_fails_closed():
    service = WorkOrderReadinessService()
    record = service.create(payload(v20_11_continuity_confirmed=False))
    assert record.state == WorkOrderReadinessState.EVIDENCE_REQUIRED


def test_risk_brain_block_is_fail_closed():
    service = WorkOrderReadinessService()
    record = service.create(payload(upstream_risk_brain_blocked=True))
    assert record.state == WorkOrderReadinessState.BLOCKED


def test_continuity_token_replay_is_rejected():
    service = WorkOrderReadinessService()
    service.create(payload())
    second = payload(source_key="source-2")
    with pytest.raises(ValueError, match="continuity token already consumed"):
        service.create(second)


def test_workspace_isolation():
    service = WorkOrderReadinessService()
    record = service.create(payload())
    assert service.get(record.id, "other") is None
    assert service.list_records("other") == []
