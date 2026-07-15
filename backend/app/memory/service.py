from uuid import UUID

from .models import MemoryCreate, MemoryRecord
from .storage import InMemoryMemoryStore


class MemoryService:
    def __init__(self, store: InMemoryMemoryStore | None = None) -> None:
        self.store = store or InMemoryMemoryStore()

    def create(self, payload: MemoryCreate) -> MemoryRecord:
        record = MemoryRecord(**payload.model_dump())
        return self.store.add(record)

    def list_all(self, category: str | None = None) -> list[MemoryRecord]:
        records = self.store.all()
        if category is None:
            return records
        normalized = category.casefold()
        return [item for item in records if item.category.casefold() == normalized]

    def search(self, query: str, category: str | None = None) -> list[MemoryRecord]:
        needle = query.strip().casefold()
        if not needle:
            return []

        records = self.list_all(category=category)
        matches = [
            item
            for item in records
            if needle in item.content.casefold()
            or needle in item.category.casefold()
            or any(needle in tag.casefold() for tag in item.tags)
        ]
        return sorted(
            matches,
            key=lambda item: (item.priority, item.created_at),
            reverse=True,
        )

    def delete(self, memory_id: UUID) -> bool:
        return self.store.delete(memory_id)


memory_service = MemoryService()
