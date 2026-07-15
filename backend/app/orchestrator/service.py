from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AgentCreate,
    AgentRecord,
    AgentStatus,
    OrchestratorStatus,
    TaskCreate,
    TaskRecord,
    TaskStatus,
)


class OrchestratorService:
    """In-memory task queue and agent registry for the first Master AI version."""

    def __init__(self) -> None:
        self._tasks: dict[UUID, TaskRecord] = {}
        self._agents: dict[UUID, AgentRecord] = {}

    def reset(self) -> None:
        self._tasks.clear()
        self._agents.clear()

    def register_agent(self, payload: AgentCreate) -> AgentRecord:
        agent = AgentRecord(**payload.model_dump())
        self._agents[agent.id] = agent
        return agent

    def list_agents(self) -> list[AgentRecord]:
        return sorted(self._agents.values(), key=lambda item: item.created_at)

    def create_task(self, payload: TaskCreate) -> TaskRecord:
        task = TaskRecord(**payload.model_dump())
        self._tasks[task.id] = task
        return task

    def list_tasks(self, status: TaskStatus | None = None) -> list[TaskRecord]:
        items = list(self._tasks.values())
        if status is not None:
            items = [item for item in items if item.status == status]
        return sorted(items, key=lambda item: (-item.priority, item.created_at))

    def get_task(self, task_id: UUID) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def update_task_status(self, task_id: UUID, status: TaskStatus) -> TaskRecord | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        task.status = status
        task.updated_at = datetime.now(timezone.utc)
        if status in {TaskStatus.completed, TaskStatus.failed, TaskStatus.blocked}:
            self._release_agent(task.assigned_agent_id)
        return task

    def assign_next(self) -> TaskRecord | None:
        queued = self.list_tasks(status=TaskStatus.queued)
        for task in queued:
            agent = self._find_agent(task.required_capabilities)
            if agent is None:
                continue
            task.assigned_agent_id = agent.id
            task.status = TaskStatus.assigned
            task.updated_at = datetime.now(timezone.utc)
            agent.status = AgentStatus.busy
            return task
        return None

    def status(self) -> OrchestratorStatus:
        tasks = list(self._tasks.values())
        agents = list(self._agents.values())
        return OrchestratorStatus(
            queued_tasks=sum(task.status == TaskStatus.queued for task in tasks),
            active_tasks=sum(
                task.status in {TaskStatus.assigned, TaskStatus.in_progress}
                for task in tasks
            ),
            completed_tasks=sum(task.status == TaskStatus.completed for task in tasks),
            registered_agents=len(agents),
            available_agents=sum(agent.status == AgentStatus.available for agent in agents),
        )

    def _find_agent(self, required_capabilities: list[str]) -> AgentRecord | None:
        required = set(required_capabilities)
        for agent in self.list_agents():
            if agent.status != AgentStatus.available:
                continue
            if required.issubset(set(agent.capabilities)):
                return agent
        return None

    def _release_agent(self, agent_id: UUID | None) -> None:
        if agent_id is None:
            return
        agent = self._agents.get(agent_id)
        if agent is not None:
            agent.status = AgentStatus.available


orchestrator_service = OrchestratorService()
