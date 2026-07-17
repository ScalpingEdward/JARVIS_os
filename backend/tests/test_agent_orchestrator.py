import pytest
from pydantic import ValidationError

from app.agent_orchestrator.models import (
    AgentRegister,
    TaskApproval,
    TaskComplete,
    TaskCreate,
    TaskPriority,
    TaskState,
)
from app.agent_orchestrator.service import AgentOrchestratorService


def test_register_dispatch_and_complete_task() -> None:
    service = AgentOrchestratorService()
    agent = service.register_agent(
        AgentRegister(name="Research Agent", capabilities=["Research", "summarize"])
    )
    task = service.create_task(
        TaskCreate(
            title="Research faceless channel niche",
            required_capability="research",
            priority=TaskPriority.HIGH,
        )
    )
    assert service.dispatch_next() is None
    service.approve_task(task.id, TaskApproval(approved=True, approved_by="Owner"))
    dispatched = service.dispatch_next()
    assert dispatched is not None
    assert dispatched.assigned_agent_id == agent.id
    assert dispatched.state == TaskState.RUNNING
    completed = service.complete_task(task.id, TaskComplete(success=True, result="Niche report"))
    assert completed is not None
    assert completed.state == TaskState.COMPLETED
    assert service.get_agent(agent.id).completed_tasks == 1


def test_dependencies_wait_until_parent_completes() -> None:
    service = AgentOrchestratorService()
    service.register_agent(AgentRegister(name="Writer", capabilities=["write"] ))
    parent = service.create_task(
        TaskCreate(title="Research", required_capability="write", requires_human_approval=False)
    )
    child = service.create_task(
        TaskCreate(
            title="Write script",
            required_capability="write",
            depends_on=[parent.id],
            requires_human_approval=False,
        )
    )
    assert child.state == TaskState.WAITING
    assert service.dispatch_next().id == parent.id
    service.complete_task(parent.id, TaskComplete(success=True, result="done"))
    dispatched = service.dispatch_next()
    assert dispatched is not None
    assert dispatched.id == child.id


def test_priority_and_capability_select_correct_task_and_agent() -> None:
    service = AgentOrchestratorService()
    research = service.register_agent(AgentRegister(name="Research", capabilities=["research"]))
    service.register_agent(AgentRegister(name="Video", capabilities=["video"] ))
    service.create_task(
        TaskCreate(
            title="Low research",
            required_capability="research",
            priority=TaskPriority.LOW,
            requires_human_approval=False,
        )
    )
    high = service.create_task(
        TaskCreate(
            title="Critical research",
            required_capability="research",
            priority=TaskPriority.CRITICAL,
            requires_human_approval=False,
        )
    )
    dispatched = service.dispatch_next()
    assert dispatched is not None
    assert dispatched.id == high.id
    assert dispatched.assigned_agent_id == research.id


def test_failed_task_retries_then_fails() -> None:
    service = AgentOrchestratorService()
    service.register_agent(AgentRegister(name="Poster", capabilities=["post"] ))
    task = service.create_task(
        TaskCreate(
            title="Prepare post",
            required_capability="post",
            max_retries=1,
            requires_human_approval=False,
        )
    )
    service.dispatch_next()
    retried = service.complete_task(task.id, TaskComplete(success=False, error="temporary"))
    assert retried.state == TaskState.QUEUED
    assert retried.retry_count == 1
    service.dispatch_next()
    failed = service.complete_task(task.id, TaskComplete(success=False, error="permanent"))
    assert failed.state == TaskState.FAILED


def test_denied_approval_cancels_task() -> None:
    service = AgentOrchestratorService()
    task = service.create_task(TaskCreate(title="Publish", required_capability="publish"))
    denied = service.approve_task(task.id, TaskApproval(approved=False, approved_by="Admin"))
    assert denied.state == TaskState.CANCELLED
    assert "Admin" in denied.error


def test_status_counts_and_safety_validation() -> None:
    service = AgentOrchestratorService()
    service.register_agent(AgentRegister(name="Agent", capabilities=["research"]))
    service.create_task(
        TaskCreate(title="Queued", required_capability="research", requires_human_approval=False)
    )
    status = service.status()
    assert status.registered_agents == 1
    assert status.queued_tasks == 1
    assert status.automatic_external_actions is False
    with pytest.raises(ValidationError):
        TaskCreate(
            title="Unsafe",
            required_capability="publish",
            automatic_external_action=True,
        )
