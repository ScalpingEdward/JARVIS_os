import pytest

from app.modules.executive_priority_engine.models import (
    PriorityCandidate,
    PriorityCreate,
    PriorityExecuteRequest,
    PriorityState,
    StrategicObjectiveEvidence,
)
from app.modules.executive_priority_engine.service import ExecutivePriorityService


def payload(**overrides):
    evidence = StrategicObjectiveEvidence(
        objective_record_id="objective-1",
        objective_state="approved",
        approval_token="objective-token-123",
        objective="deliver resilient multi-agent operations",
        success_metrics=["99.9% governed runtime availability"],
        constraints=["no autonomous risk increase"],
        dependencies=["observability"],
        business_value=90,
        urgency=80,
        confidence=85,
        estimated_effort=21,
        estimated_cost=20000,
        risk_exposure=45,
        time_criticality=75,
        opportunity_enablement=80,
        human_approved=True,
    )
    candidates = [
        PriorityCandidate(
            candidate_key="runtime-guard",
            title="Runtime resilience guard",
            impact_score=92,
            customer_value=85,
            strategic_alignment=95,
            urgency=88,
            confidence=90,
            risk_reduction=92,
            effort_points=5,
            estimated_cost=5000,
            dependencies=["observability"],
        ),
        PriorityCandidate(
            candidate_key="dashboard",
            title="Executive dashboard",
            impact_score=70,
            customer_value=75,
            strategic_alignment=80,
            urgency=55,
            confidence=85,
            risk_reduction=35,
            effort_points=8,
            estimated_cost=8000,
        ),
    ]
    data = dict(
        workspace_id="alpha",
        source_key="priority-source-1",
        actor_id="operator",
        v21_01_approved=True,
        upstream_risk_brain_blocked=False,
        evidence=evidence,
        candidates=candidates,
        dependency_status={"observability": True},
    )
    data.update(overrides)
    return PriorityCreate(**data)


def test_ranks_candidates_and_approves_order():
    service = ExecutivePriorityService()
    record = service.create(payload())
    assert record.state in {PriorityState.PRIORITIZED, PriorityState.HUMAN_REVIEW_REQUIRED}
    assert record.ranking[0].candidate_key == "runtime-guard"
    assert record.ranking[0].priority_score >= record.ranking[1].priority_score

    approved = service.execute(
        record.id,
        "alpha",
        PriorityExecuteRequest(action="approve", actor_id="owner", human_approved=True),
    )
    assert approved.state == PriorityState.APPROVED
    assert approved.approval_token

    issued = service.execute(
        record.id,
        "alpha",
        PriorityExecuteRequest(
            action="issue-to-capacity-planning",
            actor_id="owner",
            human_approved=True,
            capacity_planning_receipt_id="capacity-receipt-1",
        ),
    )
    assert issued.state == PriorityState.ISSUED_TO_CAPACITY_PLANNING


def test_dependency_block_reduces_candidate_and_prevents_all_blocked_portfolio():
    service = ExecutivePriorityService()
    request = payload(dependency_status={"observability": False})
    request.candidates[1].dependencies = ["observability"]
    record = service.create(request)
    assert record.state == PriorityState.BLOCKED
    assert all(item.blocked for item in record.ranking)


def test_missing_v21_01_evidence_fails_closed():
    service = ExecutivePriorityService()
    record = service.create(payload(v21_01_approved=False))
    assert record.state == PriorityState.EVIDENCE_REQUIRED


def test_risk_brain_block_is_authoritative():
    service = ExecutivePriorityService()
    record = service.create(payload(upstream_risk_brain_blocked=True))
    assert record.state == PriorityState.BLOCKED


def test_high_risk_portfolio_requires_human_review():
    service = ExecutivePriorityService()
    request = payload()
    request.evidence.risk_exposure = 90
    record = service.create(request)
    assert record.state == PriorityState.HUMAN_REVIEW_REQUIRED


def test_approval_requires_human_authorization():
    service = ExecutivePriorityService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="human approval required"):
        service.execute(
            record.id,
            "alpha",
            PriorityExecuteRequest(action="approve", actor_id="agent"),
        )


def test_duplicate_source_and_objective_token_rejected():
    service = ExecutivePriorityService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
    with pytest.raises(ValueError, match="approval token already consumed"):
        service.create(payload(source_key="priority-source-2"))


def test_workspace_isolation():
    service = ExecutivePriorityService()
    record = service.create(payload())
    assert service.get(record.id, "other") is None
    assert service.list_records("other") == []
    assert service.audit_records("other") == []
