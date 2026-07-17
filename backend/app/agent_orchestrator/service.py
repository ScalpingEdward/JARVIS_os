from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AgentRecord,
    AgentRegister,
    AgentState,
    OrchestratorStatus,
    TaskApproval,
    TaskComplete,
    TaskCreate,
    TaskRecord,
    TaskState,
)


class AgentOrchestratorService:
    def __init__(self) -> None:
        self._agents: dict[UUID, AgentRecord] = {}
        self._tasks: dict[UUID, TaskRecord] = {}

    def status(self) -> OrchestratorStatus:
        tasks = list(self._tasks.values())
        return OrchestratorStatus(
            registered_agents=len(self._agents),
            queued_tasks=sum(item.state == TaskState.QUEUED for item in tasks),
            running_tasks=sum(item.state == TaskState.RUNNING for item in tasks),
            waiting_tasks=sum(item.state == TaskState.WAITING for item in tasks),
            failed_tasks=sum(item.state == TaskState.FAILED for item in tasks),
            completed_tasks=sum(item.state == TaskState.COMPLETED for item in tasks),
        )

    def register_agent(self, payload: AgentRegister) -> AgentRecord:
        capabilities = self._normalize(payload.capabilities)
        agent = AgentRecord(
            name=payload.name.strip(),
            version=payload.version.strip(),
            capabilities=capabilities,
            max_concurrent_tasks=payload.max_concurrent_tasks,
            enabled=payload.enabled,
            state=AgentState.ONLINE if payload.enabled else AgentState.OFFLINE,
        )
        self._agents[agent.id] = agent
        return agent

    def list_agents(self) -> list[AgentRecord]:
        return sorted(self._agents.values(), key=lambda item: item.created_at)

    def get_agent(self, agent_id: UUID) -> AgentRecord | None:
        return self._agents.get(agent_id)

    def heartbeat(self, agent_id: UUID) -> AgentRecord | None:
        agent = self.get_agent(agent_id)
        if agent is not None:
            agent.last_heartbeat_at = datetime.now(timezone.utc)
            if agent.enabled and agent.state in {AgentState.OFFLINE, AgentState.DEGRADED}:
                agent.state = AgentState.ONLINE
        return agent

    def create_task(self, payload: TaskCreate) -> TaskRecord:
        task = TaskRecord(
            title=payload.title.strip(),
            description=payload.description.strip(),
            required_capability=payload.required_capability.strip().lower(),
            priority=payload.priority,
            depends_on=payload.depends_on,
            max_retries=payload.max_retries,
            requires_human_approval=payload.requires_human_approval,
            automatic_external_action=False,
        )
        missing = [dependency for dependency in task.depends_on if dependency not in self._tasks]
        if missing:
            task.state = TaskState.WAITING
            task.error = "One or more dependencies do not exist."
        elif task.depends_on:
            task.state = TaskState.WAITING
        self._tasks[task.id] = task
        return task

    def list_tasks(self, state: TaskState | None = None) -> list[TaskRecord]:
        tasks = list(self._tasks.values())
        if state is not None:
            tasks = [item for item in tasks if item.state == state]
        return sorted(tasks, key=lambda item: (-int(item.priority), item.created_at))

    def get_task(self, task_id: UUID) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def approve_task(self, task_id: UUID, payload: TaskApproval) -> TaskRecord | None:
        task = self.get_task(task_id)
        if task is None:
            return None
        task.human_approved = payload.approved
        if not payload.approved:
            task.state = TaskState.CANCELLED
            task.error = f"Approval denied by {payload.approved_by.strip()}."
        elif task.state == TaskState.WAITING and self._dependencies_completed(task):
            task.state = TaskState.QUEUED
            task.error = None
        task.updated_at = datetime.now(timezone.utc)
        return task

    def dispatch_next(self) -> TaskRecord | None:
        for task in self.list_tasks():
            if task.state == TaskState.WAITING and self._dependencies_completed(task):
                task.state = TaskState.QUEUED
                task.error = None
            if task.state != TaskState.QUEUED:
                continue
            if task.requires_human_approval and not task.human_approved:
                continue
            agent = self._select_agent(task.required_capability)
            if agent is None:
                continue
            task.state = TaskState.RUNNING
            task.assigned_agent_id = agent.id
            task.updated_at = datetime.now(timezone.utc)
            agent.current_task_ids.append(task.id)
            agent.state = AgentState.BUSY
            return task
        return None

    def complete_task(self, task_id: UUID, payload: TaskComplete) -> TaskRecord | None:
        task = self.get_task(task_id)
        if task is None or task.state != TaskState.RUNNING:
            return task
        agent = self.get_agent(task.assigned_agent_id) if task.assigned_agent_id else None
        if payload.success:
            task.state = TaskState.COMPLETED
            task.result = payload.result.strip()
            task.error = None
            if agent is not None:
                agent.completed_tasks += 1
        elif task.retry_count < task.max_retries:
            task.retry_count += 1
            task.state = TaskState.QUEUED
            task.error = payload.error.strip() or "Task failed and was queued for retry."
            task.assigned_agent_id = None
        else:
            task.state = TaskState.FAILED
            task.error = payload.error.strip() or "Task failed."
            if agent is not None:
                agent.failed_tasks += 1
        if agent is not None:
            agent.current_task_ids = [item for item in agent.current_task_ids if item != task.id]
            agent.state = AgentState.BUSY if agent.current_task_ids else AgentState.ONLINE
        task.updated_at = datetime.now(timezone.utc)
        return task

    def cancel_task(self, task_id: UUID) -> TaskRecord | None:
        task = self.get_task(task_id)
        if task is None or task.state in {TaskState.COMPLETED, TaskState.CANCELLED}:
            return task
        agent = self.get_agent(task.assigned_agent_id) if task.assigned_agent_id else None
        if agent is not None:
            agent.current_task_ids = [item for item in agent.current_task_ids if item != task.id]
            agent.state = AgentState.BUSY if agent.current_task_ids else AgentState.ONLINE
        task.state = TaskState.CANCELLED
        task.updated_at = datetime.now(timezone.utc)
        return task

    def _select_agent(self, capability: str) -> AgentRecord | None:
        normalized = capability.strip().lower()
        candidates = [
            agent
            for agent in self._agents.values()
            if agent.enabled
            and agent.state in {AgentState.ONLINE, AgentState.BUSY}
            and normalized in agent.capabilities
            and len(agent.current_task_ids) < agent.max_concurrent_tasks
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda item: (len(item.current_task_ids), item.failed_tasks, item.created_at))

    def _dependencies_completed(self, task: TaskRecord) -> bool:
        return bool(task.depends_on) and all(
            dependency in self._tasks and self._tasks[dependency].state == TaskState.COMPLETED
            for dependency in task.depends_on
        )

    @staticmethod
    def _normalize(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip().lower() for value in values if value.strip()))


agent_orchestrator_service = AgentOrchestratorService()
