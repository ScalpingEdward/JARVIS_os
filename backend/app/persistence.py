from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .db_models import AgentRow, MemoryRow, TaskRow, WorkerRunRow


class PersistenceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_memory(self, record: dict) -> None:
        self.session.merge(MemoryRow(**record))
        self.session.commit()

    def list_memories(self) -> list[MemoryRow]:
        return list(self.session.scalars(select(MemoryRow).order_by(MemoryRow.created_at.desc())))

    def delete_memory(self, memory_id: str) -> bool:
        result = self.session.execute(delete(MemoryRow).where(MemoryRow.id == memory_id))
        self.session.commit()
        return bool(result.rowcount)

    def save_agent(self, record: dict) -> None:
        self.session.merge(AgentRow(**record))
        self.session.commit()

    def list_agents(self) -> list[AgentRow]:
        return list(self.session.scalars(select(AgentRow).order_by(AgentRow.created_at)))

    def get_agent(self, agent_id: str) -> AgentRow | None:
        return self.session.get(AgentRow, agent_id)

    def save_task(self, record: dict) -> None:
        record.setdefault("updated_at", datetime.now(timezone.utc))
        self.session.merge(TaskRow(**record))
        self.session.commit()

    def list_tasks(self) -> list[TaskRow]:
        return list(self.session.scalars(select(TaskRow).order_by(TaskRow.priority.desc(), TaskRow.created_at)))

    def get_task(self, task_id: str) -> TaskRow | None:
        return self.session.get(TaskRow, task_id)

    def save_worker_run(self, record: dict) -> None:
        now = datetime.now(timezone.utc)
        record.setdefault("created_at", now)
        record.setdefault("updated_at", now)
        self.session.merge(WorkerRunRow(**record))
        self.session.commit()

    def list_worker_runs(self) -> list[WorkerRunRow]:
        return list(self.session.scalars(select(WorkerRunRow).order_by(WorkerRunRow.created_at)))

    def clear_runtime_data(self) -> None:
        for model in (WorkerRunRow, TaskRow, AgentRow, MemoryRow):
            self.session.execute(delete(model))
        self.session.commit()
