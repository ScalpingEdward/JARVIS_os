from app.execution.models import WorkflowCreate, WorkflowStatus
from app.execution.scheduler import WorkflowScheduler
from app.execution.service import AutonomousExecutionService
from app.execution.storage import WorkflowStore
from app.planner.models import PlanGoal
from app.planner.service import planner_service


def test_workflow_survives_service_reconstruction(tmp_path) -> None:
    path = tmp_path / "workflows.json"
    first = AutonomousExecutionService(WorkflowStore(path))
    plan = planner_service.create_plan(PlanGoal(goal="Build persistent workflow support"))
    created = first.create(WorkflowCreate(plan=plan, auto_dispatch=False))
    first.start(created.id)

    second = AutonomousExecutionService(WorkflowStore(path))
    restored = second.get(created.id)

    assert restored.id == created.id
    assert restored.status == WorkflowStatus.running
    assert len(restored.steps) == len(plan.steps)


def test_scheduler_advances_all_running_workflows(tmp_path) -> None:
    service = AutonomousExecutionService(WorkflowStore(tmp_path / "scheduler.json"))
    plan = planner_service.create_plan(PlanGoal(goal="Build scheduler support"))
    workflow = service.create(WorkflowCreate(plan=plan, auto_dispatch=False))
    service.start(workflow.id)
    scheduler = WorkflowScheduler(service=service, interval_seconds=0.01)

    processed = scheduler.run_once()
    updated = service.get(workflow.id)

    assert processed == 1
    assert updated.steps[0].status == "ready"
    assert scheduler.cycles == 1
    assert scheduler.last_error is None


def test_scheduler_start_and_stop_are_idempotent(tmp_path) -> None:
    service = AutonomousExecutionService(WorkflowStore(tmp_path / "thread.json"))
    scheduler = WorkflowScheduler(service=service, interval_seconds=0.01)

    scheduler.start()
    scheduler.start()
    assert scheduler.running is True

    scheduler.stop()
    scheduler.stop()
    assert scheduler.running is False
