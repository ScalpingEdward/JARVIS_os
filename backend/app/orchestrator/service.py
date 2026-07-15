from datetime import datetime, timezone
from uuid import UUID

from app.db import SessionLocal
from app.persistence import PersistenceRepository

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
    """Persistent task queue and agent registry for the Master AI."""

    def reset(self) -> None:
        with SessionLocal() as session:
            PersistenceRepository(session).clear_runtime_data()

    @staticmethod
    def _agent_from_row(row) -> AgentRecord:
        return AgentRecord(
            id=UUID(row.id),
            name=row.name,
            role=row.role,
            capabilities=row.capabilities,
            status=AgentStatus(row.status),
            created_at=row.created_at,
        )

    @staticmethod
    def _task_from_row(row) -> TaskRecord:
        return TaskRecord(
            id=UUID(row.id),
            title=row.title,
            description=row.description,
            priority=row.priority,
            required_capabilities=row.required_capabilities,
            status=TaskStatus(row.status),
            assigned_agent_id=UUID(row.assigned_agent_id) if row.assigned_agent_id else None,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def register_agent(self, payload: AgentCreate) -> AgentRecord:
        agent = AgentRecord(**payload.model_dump())
        with SessionLocal() as session:
            PersistenceRepository(session).save_agent(
                {
                    "id": str(agent.id),
                    "name": agent.name,
                    "role": agent.role,
                    "capabilities": agent.capabilities,
                    "status": agent.status.value,
                    "created_at": agent.created_at,
                }
            )
        return agent

    def list_agents(self) -> list[AgentRecord]:
        with SessionLocal() as session:
            return [self._agent_from_row(row) for row in PersistenceRepository(session).list_agents()]

    def create_task(self, payload: TaskCreate) -> TaskRecord:
        task = TaskRecord(**payload.model_dump())
        self._save_task(task)
        return task

    def list_tasks(self, status: TaskStatus | None = None) -> list[TaskRecord]:
        with SessionLocal() as session:
            items = [self._task_from_row(row) for row in PersistenceRepository(session).list_tasks()]
        if status is not None:
            items = [item for item in items if item.status == status]
        return sorted(items, key=lambda item: (-item.priority, item.created_at))

    def get_task(self, task_id: UUID) -> TaskRecord | None:
        with SessionLocal() as session:
            row = PersistenceRepository(session).get_task(str(task_id))
            return self._task_from_row(row) if row else None

    def update_task_status(self, task_id: UUID, status: TaskStatus) -> TaskRecord | None:
        task = self.get_task(task_id)
        if task is None:
            return None
        task.status = status
        task.updated_at = datetime.now(timezone.utc)
        if status in {TaskStatus.completed, TaskStatus.failed, TaskStatus.blocked}:
            self._release_agent(task.assigned_agent_id)
        self._save_task(task)
        return task

    def assign_next(self) -> TaskRecord | None:
        for task in self.list_tasks(status=TaskStatus.queued):
            agent = self._find_agent(task.required_capabilities)
            if agent is None:
                continue
            task.assigned_agent_id = agent.id
            task.status = TaskStatus.assigned
            task.updated_at = datetime.now(timezone.utc)
            agent.status = AgentStatus.busy
            self._save_agent(agent)
            self._save_task(task)
            return task
        return None

    def status(self) -> OrchestratorStatus:
        tasks = self.list_tasks()
        agents = self.list_agents()
        return OrchestratorStatus(
            queued_tasks=sum(task.status == TaskStatus.queued for task in tasks),
            active_tasks=sum(task.status in {TaskStatus.assigned, TaskStatus.in_progress} for task in tasks),
            completed_tasks=sum(task.status == TaskStatus.completed for task in tasks),
            registered_agents=len(agents),
            available_agents=sum(agent.status == AgentStatus.available for agent in agents),
        )

    def _find_agent(self, required_capabilities: list[str]) -> AgentRecord | None:
        required = set(required_capabilities)
        for agent in self.list_agents():
            if agent.status == AgentStatus.available and required.issubset(set(agent.capabilities)):
                return agent
        return None

    def _release_agent(self, agent_id: UUID | None) -> None:
        if agent_id is None:
            return
        for agent in self.list_agents():
            if agent.id == agent_id:
                agent.status = AgentStatus.available
                self._save_agent(agent)
                return

    def _save_agent(self, agent: AgentRecord) -> None:
        with SessionLocal() as session:
            PersistenceRepository(session).save_agent(
                {
                    "id": str(agent.id),
                    "name": agent.name,
                    "role": agent.role,
                    "capabilities": agent.capabilities,
                    "status": agent.status.value,
                    "created_at": agent.created_at,
                }
            )

    def _save_task(self, task: TaskRecord) -> None:
        with SessionLocal() as session:
            PersistenceRepository(session).save_task(
                {
                    "id": str(task.id),
                    "title": task.title,
                    "description": task.description,
                    "priority": task.priority,
                    "required_capabilities": task.required_capabilities,
                    "status": task.status.value,
                    "assigned_agent_id": str(task.assigned_agent_id) if task.assigned_agent_id else None,
                    "created_at": task.created_at,
                    "updated_at": task.updated_at,
                }
            )


orchestrator_service = OrchestratorService()
