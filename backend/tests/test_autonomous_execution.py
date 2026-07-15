from app.execution.models import WorkflowCreate, WorkflowStatus
from app.execution.service import autonomous_execution_service
from app.planner.models import PlanGoal
from app.planner.service import planner_service
from app.runtime.models import RunStatus, RuntimeProvider, RuntimeRunUpdate, RuntimeWorkerCreate
from app.runtime.service import agent_runtime_service


def setup_function() -> None:
    autonomous_execution_service.reset()
    agent_runtime_service.reset()


def _register_worker() -> None:
    agent_runtime_service.register_worker(
        RuntimeWorkerCreate(
            name="Mock developer",
            provider=RuntimeProvider.mock,
            capabilities=[
                "architecture",
                "requirements",
                "coding",
                "python",
                "testing",
                "review",
                "security",
                "documentation",
                "release",
            ],
            max_parallel_runs=2,
        )
    )


def test_workflow_queues_only_dependency_ready_step() -> None:
    _register_worker()
    plan = planner_service.create_plan(PlanGoal(goal="Build a safe Telegram parser"))
    workflow = autonomous_execution_service.create(WorkflowCreate(plan=plan))
    autonomous_execution_service.start(workflow.id)

    result = autonomous_execution_service.tick(workflow.id)

    assert len(result.queued_step_ids) == 1
    assert result.workflow.status == WorkflowStatus.running
    assert result.workflow.steps[0].runtime_run_id is not None


def test_workflow_advances_after_runtime_completion() -> None:
    _register_worker()
    plan = planner_service.create_plan(PlanGoal(goal="Build a safe Telegram parser"))
    workflow = autonomous_execution_service.create(WorkflowCreate(plan=plan))
    autonomous_execution_service.start(workflow.id)
    autonomous_execution_service.tick(workflow.id)

    first_run = agent_runtime_service.list_runs()[0]
    agent_runtime_service.update_run(
        first_run.id,
        RuntimeRunUpdate(status=RunStatus.completed, output="Architecture ready"),
    )
    result = autonomous_execution_service.tick(workflow.id)

    assert result.workflow.steps[0].status == "completed"
    assert len(result.queued_step_ids) == 1
    assert result.workflow.steps[1].runtime_run_id is not None


def test_release_step_waits_for_human_approval() -> None:
    plan = planner_service.create_plan(PlanGoal(goal="Build a safe Telegram parser"))
    workflow = autonomous_execution_service.create(
        WorkflowCreate(plan=plan, auto_dispatch=False)
    )
    autonomous_execution_service.start(workflow.id)

    for step in workflow.steps[:-1]:
        step.status = "completed"

    result = autonomous_execution_service.tick(workflow.id)
    release = result.workflow.steps[-1]

    assert release.status == "waiting_approval"
    assert result.workflow.status == WorkflowStatus.waiting_approval

    approved = autonomous_execution_service.approve_step(workflow.id, release.step_id)
    assert approved.status == WorkflowStatus.running
    assert approved.steps[-1].approval_granted is True
