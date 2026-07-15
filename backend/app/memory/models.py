from datetime import datetime, timezone
from enum import IntEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MemoryPriority(IntEnum):
    low = 1
    normal = 2
    high = 3
    critical = 4


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)
    category: str = Field(default="general", min_length=1, max_length=100)
    priority: MemoryPriority = MemoryPriority.normal
    tags: list[str] = Field(default_factory=list, max_length=20)


class MemoryRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    content: str
    category: str
    priority: MemoryPriority
    tags: list[str]
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class MemoryListResponse(BaseModel):
    items: list[MemoryRecord]
    count: int
