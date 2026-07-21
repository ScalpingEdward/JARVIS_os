import pytest

from app.modules.engineering_capacity_planner.models import (
    CapacityPlanningCreate,
    CapacityPlanningExecuteRequest,
    CapacityPlanningState,
    CapacityResource,
    PrioritizedWorkItem,
)
from app.modules.engineering_capacity_planner.service import EngineeringCapacityPlannerService


def payload(**overrides):
    data = dict(
        workspace_id="alpha",
        source_key="priority-plan-1",
        actor_id="operator",
        v21_02_priority_approved=True,
        upstream_risk_brain_blocked=False,
        planning_horizon="sprint-42",
        max_total_cost=5000,
        work_items=[
            PrioritizedWorkItem(
                candidate_id="work-1",
                title="Build defensive broker guard",
                rank=1,
                priority_score=92,
                effort_points=5,
                required_roles=["backend"],
                required_skills=["python"],
            ),
            PrioritizedWorkItem(
                candidate_id="work-2",
                title="Add runtime health verification",
                rank=2,
                priority_score=84,
                effort_points=3,
                required_roles=["backend"],
                required_skills=["python"],
            ),
        ],
        resources=[
            CapacityResource(
                resource_id="agent-1",
                resource_type="ai-agent",
                role="backend",
                skills=["python", "fastapi"],
                available_points=8,
                max_parallel_items=2,
                hourly_cost=50,
            )
        ],
    )
    data.update(overrides)
    return CapacityPlanningCreate(**data)


def test_allocates_ranked_work_and_creates_ready_plan():
    service = EngineeringCapacityPlannerService()
    record = service.create(payload())
    assert record.state == CapacityPlanningState.PLAN_READY
    assert [item.candidate_id for item in record.allocations] == ["work-1", "work-2"]
    assert all(item.status == "allocated" for item in record.allocations)
    assert record.utilization_percent == 100


def test_approval_and_budget_handoff_require_human_authority():
    service = EngineeringCapacityPlannerService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="human approval required"):
        service.execute(record.id, "alpha", CapacityPlanningExecuteRequest(action="approve", actor_id="agent"))

    approved = service.execute(record.id, "alpha", CapacityPlanningExecuteRequest(action="approve", actor_id="owner", human_approved=True))
    assert approved.state == CapacityPlanningState.APPROVED
    assert approved.approval_token

    issued = service.execute(
        record.id,
        "alpha",
        CapacityPlanningExecuteRequest(
            action="issue-to-budget-planning",
            actor_id="owner",
            human_approved=True,
            budget_planning_receipt_id="budget-receipt-1",
        ),
    )
    assert issued.state == CapacityPlanningState.ISSUED_TO_BUDGET_PLANNING


def test_missing_v21_02_evidence_fails_closed():
    service = EngineeringCapacityPlannerService()
    record = service.create(payload(v21_02_priority_approved=False))
    assert record.state == CapacityPlanningState.EVIDENCE_REQUIRED


def test_risk_brain_block_has_precedence():
    service = EngineeringCapacityPlannerService()
    record = service.create(payload(upstream_risk_brain_blocked=True))
    assert record.state == CapacityPlanningState.BLOCKED


def test_skill_mismatch_creates_capacity_constraint_and_blocks_approval():
    service = EngineeringCapacityPlannerService()
    resources = [
        CapacityResource(
            resource_id="agent-1",
            resource_type="ai-agent",
            role="frontend",
            skills=["typescript"],
            available_points=20,
        )
    ]
    record = service.create(payload(resources=resources))
    assert record.state == CapacityPlanningState.CAPACITY_CONSTRAINED
    assert record.unallocated_candidate_ids == ["work-1", "work-2"]
    with pytest.raises(ValueError, match="unallocated work"):
        service.execute(record.id, "alpha", CapacityPlanningExecuteRequest(action="approve", actor_id="owner", human_approved=True))


def test_dependency_block_is_not_allocated():
    service = EngineeringCapacityPlannerService()
    blocked = payload().work_items[0].model_copy(update={"dependency_ready": False})
    record = service.create(payload(work_items=[blocked]))
    assert record.state == CapacityPlanningState.CAPACITY_CONSTRAINED
    assert record.allocations[0].status == "dependency-blocked"


def test_cost_ceiling_escalates_to_human_review():
    service = EngineeringCapacityPlannerService()
    record = service.create(payload(max_total_cost=100))
    assert record.state == CapacityPlanningState.HUMAN_REVIEW_REQUIRED


def test_duplicate_source_receipt_replay_and_workspace_isolation():
    service = EngineeringCapacityPlannerService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
    assert service.get(record.id, "other") is None

    service.execute(record.id, "alpha", CapacityPlanningExecuteRequest(action="approve", actor_id="owner", human_approved=True))
    service.execute(
        record.id,
        "alpha",
        CapacityPlanningExecuteRequest(action="issue-to-budget-planning", actor_id="owner", human_approved=True, budget_planning_receipt_id="receipt-1"),
    )

    second = service.create(payload(source_key="priority-plan-2"))
    service.execute(second.id, "alpha", CapacityPlanningExecuteRequest(action="approve", actor_id="owner", human_approved=True))
    with pytest.raises(ValueError, match="already consumed"):
        service.execute(
            second.id,
            "alpha",
            CapacityPlanningExecuteRequest(action="issue-to-budget-planning", actor_id="owner", human_approved=True, budget_planning_receipt_id="receipt-1"),
        )
