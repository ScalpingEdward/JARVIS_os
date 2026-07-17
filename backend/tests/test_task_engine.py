import pytest
from pydantic import ValidationError

from app.task_engine.models import (
    AgentCreate,
    AgentState,
    CheckpointCreate,
    FailureRequest,
    MemoryWrite,
    ProgressUpdate,
    TaskCreate,
    TaskMutation,
    TaskPriority,
    TaskState,
)
from app.task_engine.service import TaskEngineService


def agent_payload(workspace: str = "workspace-1") -> AgentCreate:
    return AgentCreate(
        workspace_id=workspace,
        owner_id="owner-1",
        agent_key="research-agent",
        name="Research Agent",
        role="Research and summarize",
        capabilities=["research", "summarize"],
        permissions=["knowledge.read"],
        memory_namespace="agents.research",
        max_concurrent_tasks=1,
        monthly_token_budget=1000,
        cpu_budget_seconds=100,
    )


def task_payload(agent_id, key: str = "task-1", dependencies=None) -> TaskCreate:
    return TaskCreate(
        workspace_id="workspace-1",
        owner_id="owner-1",
        agent_id=agent_id,
        task_key=key,
        title=key,
        priority=TaskPriority.HIGH,
        dependency_ids=dependencies or [],
        max_retries=1,
        token_budget=500,
        cpu_budget_seconds=50,
    )


def test_agent_task_lifecycle_and_progress():
    service = TaskEngineService()
    agent = service.create_agent(agent_payload())
    service.set_agent_state(agent.id, "workspace-1", TaskMutation(requester_id="owner-1"), AgentState.ACTIVE)
    task = service.create_task(task_payload(agent.id))
    running = service.mutate_task(task.id, "workspace-1", TaskMutation(requester_id="owner-1"), TaskState.RUNNING)
    assert running is not None and running.state == TaskState.RUNNING
    updated = service.update_progress(task.id, "workspace-1", ProgressUpdate(requester_id="owner-1", progress=0.5, consumed_tokens=100, consumed_cpu_seconds=5))
    assert updated is not None and updated.progress == 0.5
    completed = service.mutate_task(task.id, "workspace-1", TaskMutation(requester_id="owner-1"), TaskState.COMPLETED)
    assert completed is not None and completed.progress == 1.0


def test_dependencies_block_then_release():
    service = TaskEngineService()
    agent = service.create_agent(agent_payload())
    service.set_agent_state(agent.id, "workspace-1", TaskMutation(requester_id="owner-1"), AgentState.ACTIVE)
    first = service.create_task(task_payload(agent.id, "first"))
    second = service.create_task(task_payload(agent.id, "second", [first.id]))
    assert second.state == TaskState.BLOCKED
    service.mutate_task(first.id, "workspace-1", TaskMutation(requester_id="owner-1"), TaskState.COMPLETED)
    assert service.get_task(second.id, "workspace-1").state == TaskState.QUEUED


def test_retry_then_dead_letter():
    service = TaskEngineService()
    agent = service.create_agent(agent_payload())
    task = service.create_task(task_payload(agent.id))
    first = service.fail_task(task.id, "workspace-1", FailureRequest(requester_id="owner-1", error="temporary", retryable=True))
    assert first is not None and first.state == TaskState.QUEUED and first.retry_count == 1
    second = service.fail_task(task.id, "workspace-1", FailureRequest(requester_id="owner-1", error="again", retryable=True))
    assert second is not None and second.state == TaskState.DEAD_LETTER


def test_checkpoint_and_agent_memory_are_isolated():
    service = TaskEngineService()
    agent = service.create_agent(agent_payload())
    task = service.create_task(task_payload(agent.id))
    checkpoint = service.create_checkpoint(CheckpointCreate(workspace_id="workspace-1", task_id=task.id, requester_id="owner-1", sequence=1, state_data={"cursor": 12}))
    assert checkpoint.task_id == task.id
    memory = service.write_memory(MemoryWrite(workspace_id="workspace-1", agent_id=agent.id, requester_id="owner-1", key="last_topic", value="gold"))
    assert memory.namespace == "agents.research"
    assert service.list_memory("other-workspace", agent.id) == []


def test_owner_and_workspace_isolation():
    service = TaskEngineService()
    agent = service.create_agent(agent_payload())
    assert service.get_agent(agent.id, "other") is None
    assert service.set_agent_state(agent.id, "workspace-1", TaskMutation(requester_id="wrong"), AgentState.ACTIVE) is None
    with pytest.raises(ValueError):
        service.create_task(TaskCreate(workspace_id="other", owner_id="owner-1", agent_id=agent.id, task_key="x", title="x"))


def test_budget_excess_blocks_task():
    service = TaskEngineService()
    agent = service.create_agent(agent_payload())
    service.set_agent_state(agent.id, "workspace-1", TaskMutation(requester_id="owner-1"), AgentState.ACTIVE)
    task = service.create_task(task_payload(agent.id))
    service.mutate_task(task.id, "workspace-1", TaskMutation(requester_id="owner-1"), TaskState.RUNNING)
    blocked = service.update_progress(task.id, "workspace-1", ProgressUpdate(requester_id="owner-1", progress=0.2, consumed_tokens=501))
    assert blocked is not None and blocked.state == TaskState.BLOCKED


def test_safety_rejects_autonomous_execution():
    with pytest.raises(ValidationError):
        AgentCreate.model_validate({**agent_payload().model_dump(), "autonomous_external_execution": True})
    service = TaskEngineService()
    agent = service.create_agent(agent_payload())
    with pytest.raises(ValidationError):
        TaskCreate(workspace_id="workspace-1", owner_id="owner-1", agent_id=agent.id, task_key="unsafe", title="unsafe", dry_run=False)
    with pytest.raises(ValidationError):
        TaskCreate(workspace_id="workspace-1", owner_id="owner-1", agent_id=agent.id, task_key="unsafe-2", title="unsafe", execute_external_action=True)


def test_status_reports_safety_defaults():
    status = TaskEngineService().status()
    assert status.version == "8.7"
    assert status.dry_run_only is True
    assert status.autonomous_external_execution is False
