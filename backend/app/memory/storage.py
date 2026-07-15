from collections.abc import Iterable
from uuid import UUID

from .models import MemoryRecord


class InMemoryMemoryStore:
    """Temporary storage adapter; replaceable by PostgreSQL in a later phase."""

    def __init__(self) -> None:
        self._records: dict[UUID, MemoryRecord] = {}

    def add(self, record: MemoryRecord) -> MemoryRecord:
        self._records[record.id] = record
        return record

    def all(self) -> list[MemoryRecord]:
        return sorted(
            self._records.values(),
            key=lambda item: item.created_at,
            reverse=True,
        )

    def delete(self, memory_id: UUID) -> bool:
        return self._records.pop(memory_id, None) is not None

    def values(self) -> Iterable[MemoryRecord]:
        return self._records.values()

    def clear(self) -> None:
        self._records.clear()
