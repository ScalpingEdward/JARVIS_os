from datetime import datetime, timezone
from uuid import UUID

from app.runtime.models import RunStatus, RuntimeRunCreate
from app.runtime.service import RuntimeError, agent_runtime_service

from .models import (
    StepExecutionRecord,
    StepExecutionStatus,
    WorkflowCreate,
    WorkflowRecord,
    WorkflowStatus,
    WorkflowTickResponse,
)


class ExecutionError(ValueError):
    pass


class AutonomousExecutionService:
    def __init__(self) -> None:
        self._workflows: dict[UUID, WorkflowRecord] = {}

    def reset(self) -> None:
        self._workflows.clear()

    def create(self, payload: WorkflowCreate) -> WorkflowRecord:
        workflow = WorkflowRecord(
            plan=payload.plan,
            auto_dispatch=payload.auto_dispatch,
            max_parallel_steps=payload.max_parallel_steps,
            stop_on_failure=payload.stop_on_failure,
            steps=[
                StepExecutionRecord(step_id=step.id, title=step.title)
                for step in payload.plan.steps
            ],
        )
        self._workflows[workflow.id] = workflow
        return workflow

    def list_workflows(self) -> list[WorkflowRecord]:
        return sorted(self._workflows.values(), key=lambda item: item.created_at, reverse=True)

    def get(self, workflow_id: UUID) -> WorkflowRecord:
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            raise ExecutionError("Workflow not found")
        return workflow

    def start(self, workflow_id: UUID) -> WorkflowRecord:
        workflow = self.get(workflow_id)
        if workflow.status not in {WorkflowStatus.created, WorkflowStatus.paused}:
            raise ExecutionError("Workflow cannot be started from its current status")
        workflow.status = WorkflowStatus.running
        workflow.updated_at = datetime.now(timezone.utc)
        return workflow

    def pause(self, workflow_id: UUID) -> WorkflowRecord:
        workflow = self.get(workflow_id)
        if workflow.status != WorkflowStatus.running:
            raise ExecutionError("Only a running workflow can be paused")
        workflow.status = WorkflowStatus.paused
        workflow.updated_at = datetime.now(timezone.utc)
        return workflow

    def cancel(self, workflow_id: UUID) -> WorkflowRecord:
        workflow = self.get(workflow_id)
        if workflow.status in {WorkflowStatus.completed, WorkflowStatus.cancelled}:
            raise ExecutionError("Workflow is already terminal")
        workflow.status = WorkflowStatus.cancelled
        workflow.updated_at = datetime.now(timezone.utc)
        return workflow

    def approve_step(self, workflow_id: UUID, step_id: UUID) -> WorkflowRecord:
        workflow = self.get(workflow_id)
        step = self._step(workflow, step_id)
        planned = self._planned_step(workflow, step_id)
        if not planned.approval_required:
            raise ExecutionError("Step does not require approval")
        step.approval_granted = True
        if step.status == StepExecutionStatus.waiting_approval:
            step.status = StepExecutionStatus.ready
        workflow.status = WorkflowStatus.running
        workflow.updated_at = datetime.now(timezone.utc)
        return workflow

    def tick(self, workflow_id: UUID) -> WorkflowTickResponse:
        workflow = self.get(workflow_id)
        if workflow.status != WorkflowStatus.running:
            raise ExecutionError("Workflow must be running")

        self._sync_runtime(workflow)
        queued: list[UUID] = []
        waiting: list[UUID] = []
        active = sum(
            step.status in {StepExecutionStatus.queued, StepExecutionStatus.running}
            for step in workflow.steps
        )

        for step in workflow.steps:
            if step.status not in {StepExecutionStatus.pending, StepExecutionStatus.ready}:
                continue
            planned = self._planned_step(workflow, step.step_id)
            dependencies = [self._step(workflow, item) for item in planned.depends_on]
            if any(item.status == StepExecutionStatus.failed for item in dependencies):
                step.status = StepExecutionStatus.skipped
                step.error = "Dependency failed"
                continue
            if not all(item.status == StepExecutionStatus.completed for item in dependencies):
                continue
            if planned.approval_required and not step.approval_granted:
                step.status = StepExecutionStatus.waiting_approval
                waiting.append(step.step_id)
                continue
            step.status = StepExecutionStatus.ready
            if workflow.auto_dispatch and active < workflow.max_parallel_steps:
                run = agent_runtime_service.create_run(
                    RuntimeRunCreate(
                        title=planned.title,
                        payload={
                            "workflow_id": str(workflow.id),
                            "step_id": str(step.step_id),
                            "description": planned.description,
                            "preferred_worker": planned.preferred_worker.value,
                        },
                        required_capabilities=planned.required_capabilities,
                    )
                )
                step.runtime_run_id = run.id
                step.status = StepExecutionStatus.queued
                queued.append(step.step_id)
                active += 1
                try:
                    agent_runtime_service.dispatch_next()
                except RuntimeError:
                    pass

        self._refresh_workflow_status(workflow)
        workflow.updated_at = datetime.now(timezone.utc)
        return WorkflowTickResponse(
            workflow=workflow,
            queued_step_ids=queued,
            waiting_approval_step_ids=waiting,
        )

    def _sync_runtime(self, workflow: WorkflowRecord) -> None:
        runs = {run.id: run for run in agent_runtime_service.list_runs()}
        for step in workflow.steps:
            if step.runtime_run_id is None:
                continue
            run = runs.get(step.runtime_run_id)
            if run is None:
                continue
            mapping = {
                RunStatus.queued: StepExecutionStatus.queued,
                RunStatus.retrying: StepExecutionStatus.queued,
                RunStatus.running: StepExecutionStatus.running,
                RunStatus.completed: StepExecutionStatus.completed,
                RunStatus.failed: StepExecutionStatus.failed,
                RunStatus.timed_out: StepExecutionStatus.failed,
            }
            step.status = mapping[run.status]
            step.output = run.output
            step.error = run.error
            step.started_at = run.started_at
            step.finished_at = run.finished_at

    def _refresh_workflow_status(self, workflow: WorkflowRecord) -> None:
        statuses = {step.status for step in workflow.steps}
        if all(status in {StepExecutionStatus.completed, StepExecutionStatus.skipped} for status in statuses):
            workflow.status = WorkflowStatus.completed
        elif StepExecutionStatus.failed in statuses and workflow.stop_on_failure:
            workflow.status = WorkflowStatus.failed
        elif StepExecutionStatus.waiting_approval in statuses and not any(
            status in {StepExecutionStatus.queued, StepExecutionStatus.running} for status in statuses
        ):
            workflow.status = WorkflowStatus.waiting_approval

    @staticmethod
    def _step(workflow: WorkflowRecord, step_id: UUID) -> StepExecutionRecord:
        for step in workflow.steps:
            if step.step_id == step_id:
                return step
        raise ExecutionError("Workflow step not found")

    @staticmethod
    def _planned_step(workflow: WorkflowRecord, step_id: UUID):
        for step in workflow.plan.steps:
            if step.id == step_id:
                return step
        raise ExecutionError("Planned step not found")


autonomous_execution_service = AutonomousExecutionService()
