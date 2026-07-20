from uuid import uuid4

from app.executive_workflow_executor_runtime.models import (
    TaskExecutionObservation,
    WorkflowExecutorAssessmentCreate,
    WorkflowExecutorState,
)
from app.executive_workflow_executor_runtime.service import ExecutiveWorkflowExecutorRuntimeService


def valid_payload(workspace_id: str = "ws-1") -> WorkflowExecutorAssessmentCreate:
    return WorkflowExecutorAssessmentCreate(
        workspace_id=workspace_id,
        source_key="executor-1",
        actor_id="tester",
        workflow_assessment_id="workflow-1",
        workflow_state="running",
        workflow_instance_id=uuid4(),
        step_id="vision",
        target_module="executive-vision-adapter-consensus",
        worker_id="worker-vision-1",
        queue_name="workflow-tasks",
        observation=TaskExecutionObservation(
            task_persisted=True,
            queue_registered=True,
            worker_registered=True,
            worker_capability_match=True,
            lease_acquired=True,
            lease_owner_verified=True,
            heartbeat_verified=True,
            timer_persisted=True,
            timer_due=True,
            dispatch_acknowledged=True,
            result_checkpoint_persisted=True,
            graceful_shutdown_verified=True,
        ),
    )


def test_dispatches_verified_task() -> None:
    result = ExecutiveWorkflowExecutorRuntimeService().create(valid_payload())
    assert result.state == WorkflowExecutorState.dispatched
    assert result.dispatchable is True


def test_waits_for_timer() -> None:
    payload = valid_payload()
    payload.observation.timer_due = False
    assert ExecutiveWorkflowExecutorRuntimeService().create(payload).state == WorkflowExecutorState.waiting_timer


def test_rejects_worker_capability_mismatch() -> None:
    payload = valid_payload()
    payload.observation.worker_capability_match = False
    assert ExecutiveWorkflowExecutorRuntimeService().create(payload).state == WorkflowExecutorState.worker_unavailable


def test_requires_lease_heartbeat() -> None:
    payload = valid_payload()
    payload.observation.heartbeat_verified = False
    assert ExecutiveWorkflowExecutorRuntimeService().create(payload).state == WorkflowExecutorState.lease_conflict


def test_recovers_expired_lease() -> None:
    payload = valid_payload()
    payload.observation.lease_expired = True
    payload.observation.retry_checkpoint_persisted = True
    assert ExecutiveWorkflowExecutorRuntimeService().create(payload).state == WorkflowExecutorState.recovery_required


def test_risk_brain_blocks() -> None:
    payload = valid_payload()
    payload.risk_brain_clear = False
    assert ExecutiveWorkflowExecutorRuntimeService().create(payload).state == WorkflowExecutorState.blocked


def test_duplicate_task_rejected() -> None:
    service = ExecutiveWorkflowExecutorRuntimeService()
    first = valid_payload()
    service.create(first)
    second = valid_payload()
    second.source_key = "executor-2"
    second.task_id = first.task_id
    try:
        service.create(second)
    except ValueError as exc:
        assert "Duplicate workflow task" in str(exc)
    else:
        raise AssertionError("duplicate workflow task was accepted")


def test_workspace_isolation() -> None:
    service = ExecutiveWorkflowExecutorRuntimeService()
    record = service.create(valid_payload())
    assert service.get(record.id, "other") is None
