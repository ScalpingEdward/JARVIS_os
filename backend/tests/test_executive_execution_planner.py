import pytest

from app.modules.executive_execution_planner.models import (
    ExecutionCommand,
    ExecutionPlanAction,
    ExecutionPlanCreate,
    ExecutionPlanState,
    WorkPackageInput,
)
from app.modules.executive_execution_planner.service import (
    ExecutionPlanError,
    ExecutiveExecutionPlannerService,
)


def payload(workspace: str = "alpha") -> ExecutionPlanCreate:
    return ExecutionPlanCreate(
        workspace_id=workspace,
        source_key="decision-001",
        investment_decision_id="inv-001",
        investment_decision_approved=True,
        v21_08_evidence={"approval": "verified"},
        strategic_constraints=["no autonomous deployment"],
        available_capacity_points=40,
        planning_horizon_days=30,
        max_parallel_workstreams=2,
        work_packages=[
            WorkPackageInput(
                key="design",
                title="Design execution boundary",
                owner="architecture",
                effort_points=8,
                duration_days=4,
                expected_value=15000,
                allocated_budget=3000,
                deliverables=["architecture"],
                exit_criteria=["approved design"],
                rollback_plan="Discard design and retain v21.08 decision.",
            ),
            WorkPackageInput(
                key="build",
                title="Build governed capability",
                owner="engineering",
                effort_points=18,
                duration_days=8,
                expected_value=40000,
                allocated_budget=9000,
                dependencies=["design"],
                deliverables=["service", "API"],
                exit_criteria=["tests green"],
                rollback_plan="Revert feature branch.",
            ),
            WorkPackageInput(
                key="validate",
                title="Validate readiness",
                owner="quality",
                effort_points=9,
                duration_days=3,
                expected_value=10000,
                allocated_budget=2000,
                dependencies=["build"],
                deliverables=["evidence pack"],
                exit_criteria=["acceptance complete"],
                rollback_plan="Return plan to engineering.",
            ),
        ],
    )


def test_generates_ordered_plan_and_critical_path() -> None:
    service = ExecutiveExecutionPlannerService()
    record = service.create(payload(), actor="tester")
    assert record.state == ExecutionPlanState.EXECUTION_PLAN_READY
    assert [item.key for item in record.work_packages] == ["design", "build", "validate"]
    assert record.critical_path == ["design", "build", "validate"]
    assert record.execution_readiness_score == 100
    assert record.total_budget == 14000


def test_requires_v21_08_evidence() -> None:
    service = ExecutiveExecutionPlannerService()
    request = payload()
    request.v21_08_evidence = {}
    record = service.create(request)
    assert record.state == ExecutionPlanState.EVIDENCE_REQUIRED


def test_risk_brain_hard_block_is_authoritative() -> None:
    service = ExecutiveExecutionPlannerService()
    request = payload()
    request.risk_brain_hard_block = True
    record = service.create(request)
    assert record.state == ExecutionPlanState.BLOCKED


def test_capacity_shortage_requires_human_review() -> None:
    service = ExecutiveExecutionPlannerService()
    request = payload()
    request.available_capacity_points = 10
    record = service.create(request)
    assert record.state == ExecutionPlanState.HUMAN_REVIEW_REQUIRED
    assert record.bottlenecks


def test_approval_and_issue_replay_protection() -> None:
    service = ExecutiveExecutionPlannerService()
    record = service.create(payload())
    approved = service.execute(
        "alpha",
        record.id,
        ExecutionPlanAction(command=ExecutionCommand.APPROVE, actor="owner", approval_token="token-1"),
    )
    assert approved.state == ExecutionPlanState.APPROVED
    issued = service.execute(
        "alpha",
        record.id,
        ExecutionPlanAction(command=ExecutionCommand.ISSUE, actor="owner", downstream_receipt="receipt-1"),
    )
    assert issued.state == ExecutionPlanState.ISSUED_TO_ORCHESTRATOR

    second = payload()
    second.source_key = "decision-002"
    second.investment_decision_id = "inv-002"
    other = service.create(second)
    with pytest.raises(ExecutionPlanError, match="approval token replay"):
        service.execute(
            "alpha",
            other.id,
            ExecutionPlanAction(command=ExecutionCommand.APPROVE, actor="owner", approval_token="token-1"),
        )


def test_duplicate_source_and_workspace_isolation() -> None:
    service = ExecutiveExecutionPlannerService()
    record = service.create(payload())
    with pytest.raises(ExecutionPlanError, match="duplicate source_key"):
        service.create(payload())
    with pytest.raises(ExecutionPlanError, match="record not found"):
        service.get("other", record.id)


def test_cyclic_dependencies_are_rejected() -> None:
    service = ExecutiveExecutionPlannerService()
    request = payload()
    request.work_packages[0].dependencies = ["validate"]
    with pytest.raises(ExecutionPlanError, match="cyclic dependency"):
        service.create(request)
