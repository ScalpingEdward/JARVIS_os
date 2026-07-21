import pytest

from app.modules.budget_allocation_engine.models import (
    BudgetAllocationCreate,
    BudgetAllocationExecuteRequest,
    BudgetAllocationState,
    BudgetEnvelope,
    CapacityAllocationEvidence,
)
from app.modules.budget_allocation_engine.service import BudgetAllocationService


def payload(**overrides) -> BudgetAllocationCreate:
    data = dict(
        workspace_id="alpha",
        source_key="capacity-plan-1",
        actor_id="executive",
        v21_03_capacity_approved=True,
        upstream_risk_brain_blocked=False,
        evidence=CapacityAllocationEvidence(
            capacity_record_id="capacity-1",
            capacity_state="approved",
            approval_token="capacity-token-123",
            total_effort_points=40,
            allocated_effort_points=36,
            estimated_labor_cost=12000,
            estimated_ai_cost=1800,
            estimated_cloud_cost=1200,
            workstream_ids=["ws-1", "ws-2"],
            dependency_blocked_workstreams=[],
            human_approved=True,
        ),
        envelope=BudgetEnvelope(
            total_budget=18000,
            labor_budget=13000,
            ai_budget=2500,
            cloud_budget=1500,
            contingency_budget=1800,
            reserve_ratio=0.10,
            hard_cost_ceiling=18000,
        ),
        strategic_priority_score=90,
        expected_business_value=50000,
        target_period="2026-Q4",
    )
    data.update(overrides)
    return BudgetAllocationCreate(**data)


def test_prepares_affordable_budget_plan():
    service = BudgetAllocationService()
    record = service.create(payload())
    assert record.state == BudgetAllocationState.PLAN_READY
    assert record.plan is not None
    assert record.plan.total_allocated == 15000
    assert record.plan.contingency_reserved == 1800
    assert record.plan.projected_roi is not None


def test_approval_and_roadmap_issuance_require_human_control():
    service = BudgetAllocationService()
    record = service.create(payload())

    with pytest.raises(ValueError, match="human approval required"):
        service.execute(record.id, "alpha", BudgetAllocationExecuteRequest(action="approve", actor_id="agent"))

    approved = service.execute(
        record.id,
        "alpha",
        BudgetAllocationExecuteRequest(action="approve", actor_id="owner", human_approved=True),
    )
    assert approved.state == BudgetAllocationState.APPROVED
    assert approved.approval_token

    issued = service.execute(
        record.id,
        "alpha",
        BudgetAllocationExecuteRequest(
            action="issue-to-roadmap",
            actor_id="owner",
            human_approved=True,
            roadmap_receipt_id="roadmap-receipt-1",
        ),
    )
    assert issued.state == BudgetAllocationState.ISSUED_TO_ROADMAP


def test_budget_shortfall_requires_human_review():
    service = BudgetAllocationService()
    constrained = payload(
        source_key="capacity-plan-2",
        evidence=payload().evidence.model_copy(update={"approval_token": "capacity-token-456"}),
        envelope=BudgetEnvelope(
            total_budget=9000,
            labor_budget=7000,
            ai_budget=1000,
            cloud_budget=500,
            contingency_budget=900,
            reserve_ratio=0.10,
        ),
    )
    record = service.create(constrained)
    assert record.state == BudgetAllocationState.HUMAN_REVIEW_REQUIRED
    assert record.plan is not None
    assert record.plan.total_allocated < record.plan.total_requested


def test_missing_capacity_evidence_fails_closed():
    service = BudgetAllocationService()
    record = service.create(payload(v21_03_capacity_approved=False))
    assert record.state == BudgetAllocationState.EVIDENCE_REQUIRED


def test_risk_brain_block_is_authoritative():
    service = BudgetAllocationService()
    record = service.create(payload(upstream_risk_brain_blocked=True))
    assert record.state == BudgetAllocationState.BLOCKED


def test_dependency_blocked_work_receives_no_budget():
    service = BudgetAllocationService()
    evidence = payload().evidence.model_copy(
        update={"dependency_blocked_workstreams": ["ws-2"]}
    )
    record = service.create(payload(evidence=evidence))
    assert record.state == BudgetAllocationState.BLOCKED
    assert record.plan is None


def test_capacity_token_and_roadmap_receipt_replay_are_rejected():
    service = BudgetAllocationService()
    first = service.create(payload())
    with pytest.raises(ValueError, match="capacity approval token already consumed"):
        service.create(payload(source_key="capacity-plan-replay"))

    service.execute(
        first.id,
        "alpha",
        BudgetAllocationExecuteRequest(action="approve", actor_id="owner", human_approved=True),
    )
    service.execute(
        first.id,
        "alpha",
        BudgetAllocationExecuteRequest(
            action="issue-to-roadmap",
            actor_id="owner",
            human_approved=True,
            roadmap_receipt_id="receipt-replay",
        ),
    )

    second_payload = payload(
        source_key="capacity-plan-3",
        evidence=payload().evidence.model_copy(update={"approval_token": "capacity-token-789"}),
    )
    second = service.create(second_payload)
    service.execute(
        second.id,
        "alpha",
        BudgetAllocationExecuteRequest(action="approve", actor_id="owner", human_approved=True),
    )
    with pytest.raises(ValueError, match="roadmap receipt already consumed"):
        service.execute(
            second.id,
            "alpha",
            BudgetAllocationExecuteRequest(
                action="issue-to-roadmap",
                actor_id="owner",
                human_approved=True,
                roadmap_receipt_id="receipt-replay",
            ),
        )


def test_workspace_isolation_and_audit():
    service = BudgetAllocationService()
    record = service.create(payload())
    assert service.get(record.id, "other") is None
    assert service.list_records("other") == []
    assert len(service.audit_records("alpha")) == 1
