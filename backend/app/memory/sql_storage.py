from uuid import UUID

from app.db import SessionLocal
from app.memory.models import MemoryRecord
from app.persistence import PersistenceRepository


class SQLMemoryStore:
    def add(self, record: MemoryRecord) -> MemoryRecord:
        with SessionLocal() as session:
            PersistenceRepository(session).save_memory(
                {
                    "id": str(record.id),
                    "content": record.content,
                    "category": record.category,
                    "tags": record.tags,
                    "priority": record.priority,
                    "created_at": record.created_at,
                }
            )
        return record

    def all(self) -> list[MemoryRecord]:
        with SessionLocal() as session:
            rows = PersistenceRepository(session).list_memories()
            return [
                MemoryRecord(
                    id=UUID(row.id),
                    content=row.content,
                    category=row.category,
                    tags=row.tags,
                    priority=row.priority,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    def delete(self, memory_id: UUID) -> bool:
        with SessionLocal() as session:
            return PersistenceRepository(session).delete_memory(str(memory_id))

    def clear(self) -> None:
        with SessionLocal() as session:
            repo = PersistenceRepository(session)
            for record in repo.list_memories():
                repo.delete_memory(record.id)
