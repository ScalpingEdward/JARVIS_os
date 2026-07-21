from datetime import date, timedelta

import pytest

from app.modules.executive_roadmap_generator.models import (
    FundedWorkstream,
    RoadmapCreate,
    RoadmapExecuteRequest,
    RoadmapState,
)
from app.modules.executive_roadmap_generator.service import ExecutiveRoadmapService


def payload(**overrides):
    data = dict(
        workspace_id="alpha",
        source_key="budget-plan-1",
        actor_id="operator",
        v21_04_budget_approved=True,
        upstream_risk_brain_blocked=False,
        budget_approval_token="budget-token-123",
        planning_horizon_days=120,
        max_parallel_workstreams=2,
        strategic_constraints=["no risk increase", "human approval before execution"],
        workstreams=[
            FundedWorkstream(
                workstream_id="ws-1",
                title="Strengthen runtime resilience",
                priority_rank=1,
                effort_points=8,
                allocated_budget=4000,
                expected_value=12000,
                dependencies=["observability"],
                dependency_ready=True,
                owner_role="platform-engineering",
            ),
            FundedWorkstream(
                workstream_id="ws-2",
                title="Improve executive telemetry",
                priority_rank=2,
                effort_points=5,
                allocated_budget=2500,
                expected_value=7000,
                dependencies=[],
                dependency_ready=True,
                owner_role="data-engineering",
            ),
        ],
    )
    data.update(overrides)
    return RoadmapCreate(**data)


def test_generates_roadmap_then_approves_and_issues():
    service = ExecutiveRoadmapService()
    record = service.create(payload())
    assert record.state == RoadmapState.HUMAN_REVIEW_REQUIRED
    assert len(record.milestones) == 2
    assert record.total_budget == 6500

    approved = service.execute(
        record.id,
        "alpha",
        RoadmapExecuteRequest(action="approve-roadmap", actor_id="owner", human_approved=True),
    )
    assert approved.state == RoadmapState.APPROVED
    assert approved.approval_token

    issued = service.execute(
        record.id,
        "alpha",
        RoadmapExecuteRequest(
            action="issue-to-kpi",
            actor_id="owner",
            human_approved=True,
            kpi_receipt_id="kpi-receipt-1",
        ),
    )
    assert issued.state == RoadmapState.ISSUED_TO_KPI


def test_dependency_block_fails_closed():
    service = ExecutiveRoadmapService()
    blocked = payload().workstreams[0].model_copy(update={"dependency_ready": False})
    record = service.create(payload(workstreams=[blocked]))
    assert record.state == RoadmapState.BLOCKED


def test_missing_budget_evidence_is_rejected():
    service = ExecutiveRoadmapService()
    record = service.create(payload(v21_04_budget_approved=False))
    assert record.state == RoadmapState.EVIDENCE_REQUIRED


def test_risk_brain_block_is_authoritative():
    service = ExecutiveRoadmapService()
    record = service.create(payload(upstream_risk_brain_blocked=True))
    assert record.state == RoadmapState.BLOCKED


def test_target_date_conflict_is_detected():
    service = ExecutiveRoadmapService()
    constrained = payload().workstreams[0].model_copy(
        update={"target_end": date.today() + timedelta(days=2), "effort_points": 10}
    )
    record = service.create(payload(workstreams=[constrained]))
    assert record.state == RoadmapState.SCHEDULE_CONFLICT


def test_human_approval_is_required():
    service = ExecutiveRoadmapService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="human approval required"):
        service.execute(
            record.id,
            "alpha",
            RoadmapExecuteRequest(action="approve-roadmap", actor_id="agent"),
        )


def test_budget_token_and_receipt_replay_are_rejected():
    service = ExecutiveRoadmapService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="budget approval token already consumed"):
        service.create(payload(source_key="budget-plan-2"))

    service.execute(record.id, "alpha", RoadmapExecuteRequest(
        action="approve-roadmap", actor_id="owner", human_approved=True
    ))
    service.execute(record.id, "alpha", RoadmapExecuteRequest(
        action="issue-to-kpi", actor_id="owner", human_approved=True, kpi_receipt_id="receipt-1"
    ))

    second = service.create(payload(
        source_key="budget-plan-3",
        budget_approval_token="budget-token-456",
    ))
    service.execute(second.id, "alpha", RoadmapExecuteRequest(
        action="approve-roadmap", actor_id="owner", human_approved=True
    ))
    with pytest.raises(ValueError, match="kpi receipt already consumed"):
        service.execute(second.id, "alpha", RoadmapExecuteRequest(
            action="issue-to-kpi", actor_id="owner", human_approved=True, kpi_receipt_id="receipt-1"
        ))


def test_workspace_isolation():
    service = ExecutiveRoadmapService()
    record = service.create(payload())
    assert service.get(record.id, "other") is None
    assert service.list_records("other") == []
    assert service.audit_records("other") == []
