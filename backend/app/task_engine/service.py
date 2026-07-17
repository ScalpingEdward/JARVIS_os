from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AgentCreate,
    AgentRecord,
    AgentState,
    CheckpointCreate,
    CheckpointRecord,
    FailureRequest,
    MemoryRecord,
    MemoryWrite,
    ProgressUpdate,
    TaskCreate,
    TaskEngineStatus,
    TaskEvent,
    TaskMutation,
    TaskPriority,
    TaskRecord,
    TaskState,
)


class TaskEngineService:
    def __init__(self) -> None:
        self.agents: dict[UUID, AgentRecord] = {}
        self.tasks: dict[UUID, TaskRecord] = {}
        self.checkpoints: dict[UUID, CheckpointRecord] = {}
        self.memory: dict[tuple[UUID, str], MemoryRecord] = {}
        self.events: list[TaskEvent] = []

    def _event(self, workspace_id: str, event_type: str, actor_id: str, *, task_id: UUID | None = None, agent_id: UUID | None = None, details: dict | None = None) -> None:
        self.events.append(TaskEvent(workspace_id=workspace_id, task_id=task_id, agent_id=agent_id, event_type=event_type, actor_id=actor_id, details=details or {}))

    def status(self) -> TaskEngineStatus:
        values = list(self.tasks.values())
        return TaskEngineStatus(
            agents=len(self.agents), tasks=len(values),
            queued=sum(t.state == TaskState.QUEUED for t in values),
            running=sum(t.state == TaskState.RUNNING for t in values),
            blocked=sum(t.state == TaskState.BLOCKED for t in values),
            dead_letter=sum(t.state == TaskState.DEAD_LETTER for t in values),
            checkpoints=len(self.checkpoints), memory_records=len(self.memory),
        )

    def create_agent(self, payload: AgentCreate) -> AgentRecord:
        if any(a.workspace_id == payload.workspace_id and a.agent_key == payload.agent_key for a in self.agents.values()):
            raise ValueError("agent key already exists in workspace")
        item = AgentRecord(**payload.model_dump(exclude={"human_approved", "autonomous_external_execution"}))
        self.agents[item.id] = item
        self._event(item.workspace_id, "agent.created", item.owner_id, agent_id=item.id)
        return item

    def list_agents(self, workspace_id: str) -> list[AgentRecord]:
        return [a for a in self.agents.values() if a.workspace_id == workspace_id]

    def get_agent(self, agent_id: UUID, workspace_id: str) -> AgentRecord | None:
        item = self.agents.get(agent_id)
        return item if item and item.workspace_id == workspace_id else None

    def set_agent_state(self, agent_id: UUID, workspace_id: str, payload: TaskMutation, state: AgentState) -> AgentRecord | None:
        item = self.get_agent(agent_id, workspace_id)
        if not item or item.owner_id != payload.requester_id:
            return None
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        self._event(workspace_id, f"agent.{state.value}", payload.requester_id, agent_id=agent_id, details={"reason": payload.reason})
        return item

    def create_task(self, payload: TaskCreate) -> TaskRecord:
        agent = self.get_agent(payload.agent_id, payload.workspace_id)
        if not agent or agent.owner_id != payload.owner_id:
            raise ValueError("owned agent not found")
        if any(t.workspace_id == payload.workspace_id and t.task_key == payload.task_key for t in self.tasks.values()):
            raise ValueError("task key already exists in workspace")
        dependencies = [self.tasks.get(task_id) for task_id in payload.dependency_ids]
        if any(task is None or task.workspace_id != payload.workspace_id for task in dependencies):
            raise ValueError("task dependency not found in workspace")
        state = TaskState.BLOCKED if any(task.state != TaskState.COMPLETED for task in dependencies if task) else TaskState.QUEUED
        item = TaskRecord(**payload.model_dump(exclude={"dry_run", "human_approved", "execute_external_action"}), state=state)
        if state == TaskState.BLOCKED:
            item.blocked_reason = "waiting for dependencies"
        self.tasks[item.id] = item
        self._event(item.workspace_id, "task.created", item.owner_id, task_id=item.id, agent_id=item.agent_id, details={"state": item.state.value})
        return item

    def list_tasks(self, workspace_id: str, agent_id: UUID | None = None) -> list[TaskRecord]:
        items = [t for t in self.tasks.values() if t.workspace_id == workspace_id and (agent_id is None or t.agent_id == agent_id)]
        rank = {TaskPriority.CRITICAL: 0, TaskPriority.HIGH: 1, TaskPriority.NORMAL: 2, TaskPriority.LOW: 3}
        return sorted(items, key=lambda t: (rank[t.priority], t.created_at))

    def get_task(self, task_id: UUID, workspace_id: str) -> TaskRecord | None:
        item = self.tasks.get(task_id)
        return item if item and item.workspace_id == workspace_id else None

    def queue(self, workspace_id: str) -> list[TaskRecord]:
        self._release_dependencies(workspace_id)
        return [t for t in self.list_tasks(workspace_id) if t.state in {TaskState.QUEUED, TaskState.BLOCKED}]

    def _release_dependencies(self, workspace_id: str) -> None:
        for task in self.tasks.values():
            if task.workspace_id != workspace_id or task.state != TaskState.BLOCKED:
                continue
            dependencies = [self.tasks.get(dep) for dep in task.dependency_ids]
            if dependencies and all(dep and dep.state == TaskState.COMPLETED for dep in dependencies):
                task.state = TaskState.QUEUED
                task.blocked_reason = None
                task.updated_at = datetime.now(timezone.utc)
                self._event(workspace_id, "task.dependencies_released", task.owner_id, task_id=task.id, agent_id=task.agent_id)

    def mutate_task(self, task_id: UUID, workspace_id: str, payload: TaskMutation, state: TaskState) -> TaskRecord | None:
        item = self.get_task(task_id, workspace_id)
        if not item or item.owner_id != payload.requester_id:
            return None
        if state == TaskState.RUNNING:
            agent = self.get_agent(item.agent_id, workspace_id)
            if not agent or agent.state != AgentState.ACTIVE:
                item.state = TaskState.BLOCKED
                item.blocked_reason = "agent is not active"
                return item
            running = sum(t.agent_id == agent.id and t.state == TaskState.RUNNING for t in self.tasks.values())
            if running >= agent.max_concurrent_tasks:
                item.state = TaskState.BLOCKED
                item.blocked_reason = "agent concurrency limit reached"
                return item
            if any(self.tasks.get(dep) is None or self.tasks[dep].state != TaskState.COMPLETED for dep in item.dependency_ids):
                item.state = TaskState.BLOCKED
                item.blocked_reason = "waiting for dependencies"
                return item
        item.state = state
        item.blocked_reason = None
        if state == TaskState.COMPLETED:
            item.progress = 1.0
        item.updated_at = datetime.now(timezone.utc)
        self._event(workspace_id, f"task.{state.value}", payload.requester_id, task_id=item.id, agent_id=item.agent_id, details={"reason": payload.reason})
        if state == TaskState.COMPLETED:
            self._release_dependencies(workspace_id)
        return item

    def update_progress(self, task_id: UUID, workspace_id: str, payload: ProgressUpdate) -> TaskRecord | None:
        item = self.get_task(task_id, workspace_id)
        if not item or item.owner_id != payload.requester_id or item.state != TaskState.RUNNING:
            return None
        agent = self.get_agent(item.agent_id, workspace_id)
        new_tokens = item.consumed_tokens + payload.consumed_tokens
        new_cpu = item.consumed_cpu_seconds + payload.consumed_cpu_seconds
        if (item.token_budget and new_tokens > item.token_budget) or (item.cpu_budget_seconds and new_cpu > item.cpu_budget_seconds):
            item.state = TaskState.BLOCKED
            item.blocked_reason = "task resource budget exceeded"
            return item
        if agent and ((agent.monthly_token_budget and agent.consumed_tokens + payload.consumed_tokens > agent.monthly_token_budget) or (agent.cpu_budget_seconds and agent.consumed_cpu_seconds + payload.consumed_cpu_seconds > agent.cpu_budget_seconds)):
            item.state = TaskState.BLOCKED
            item.blocked_reason = "agent resource budget exceeded"
            return item
        item.progress = payload.progress
        item.consumed_tokens = new_tokens
        item.consumed_cpu_seconds = new_cpu
        if agent:
            agent.consumed_tokens += payload.consumed_tokens
            agent.consumed_cpu_seconds += payload.consumed_cpu_seconds
        item.updated_at = datetime.now(timezone.utc)
        self._event(workspace_id, "task.progress", payload.requester_id, task_id=item.id, agent_id=item.agent_id, details={"progress": item.progress})
        return item

    def fail_task(self, task_id: UUID, workspace_id: str, payload: FailureRequest) -> TaskRecord | None:
        item = self.get_task(task_id, workspace_id)
        if not item or item.owner_id != payload.requester_id:
            return None
        item.last_error = payload.error
        if payload.retryable and item.retry_count < item.max_retries:
            item.retry_count += 1
            item.state = TaskState.QUEUED
        else:
            item.state = TaskState.DEAD_LETTER
        item.updated_at = datetime.now(timezone.utc)
        self._event(workspace_id, "task.failed", payload.requester_id, task_id=item.id, agent_id=item.agent_id, details={"retry_count": item.retry_count, "state": item.state.value})
        return item

    def create_checkpoint(self, payload: CheckpointCreate) -> CheckpointRecord:
        task = self.get_task(payload.task_id, payload.workspace_id)
        if not task or task.owner_id != payload.requester_id:
            raise ValueError("owned task not found")
        if any(c.task_id == payload.task_id and c.sequence == payload.sequence for c in self.checkpoints.values()):
            raise ValueError("checkpoint sequence already exists")
        item = CheckpointRecord(**payload.model_dump(exclude={"human_approved"}))
        self.checkpoints[item.id] = item
        task.checkpoint_id = item.id
        self._event(payload.workspace_id, "checkpoint.created", payload.requester_id, task_id=task.id, agent_id=task.agent_id, details={"sequence": item.sequence})
        return item

    def list_checkpoints(self, workspace_id: str, task_id: UUID | None = None) -> list[CheckpointRecord]:
        return [c for c in self.checkpoints.values() if c.workspace_id == workspace_id and (task_id is None or c.task_id == task_id)]

    def write_memory(self, payload: MemoryWrite) -> MemoryRecord:
        agent = self.get_agent(payload.agent_id, payload.workspace_id)
        if not agent or agent.owner_id != payload.requester_id:
            raise ValueError("owned agent not found")
        key = (agent.id, payload.key)
        record = self.memory.get(key)
        if record:
            record.value = payload.value
            record.tags = payload.tags
            record.updated_at = datetime.now(timezone.utc)
        else:
            record = MemoryRecord(workspace_id=payload.workspace_id, agent_id=agent.id, namespace=agent.memory_namespace, key=payload.key, value=payload.value, tags=payload.tags)
            self.memory[key] = record
        self._event(payload.workspace_id, "memory.written", payload.requester_id, agent_id=agent.id, details={"key": payload.key})
        return record

    def list_memory(self, workspace_id: str, agent_id: UUID) -> list[MemoryRecord]:
        return [m for m in self.memory.values() if m.workspace_id == workspace_id and m.agent_id == agent_id]

    def list_events(self, workspace_id: str) -> list[TaskEvent]:
        return [event for event in self.events if event.workspace_id == workspace_id]


task_engine_service = TaskEngineService()
