from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class MemoryType(str, Enum):
    FACT = "fact"
    PREFERENCE = "preference"
    DECISION = "decision"
    PROCEDURE = "procedure"
    EVENT = "event"
    LESSON = "lesson"


class MemoryVisibility(str, Enum):
    PRIVATE = "private"
    WORKSPACE = "workspace"
    SHARED = "shared"


class MemoryState(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MemoryCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20000)
    memory_type: MemoryType = MemoryType.FACT
    visibility: MemoryVisibility = MemoryVisibility.PRIVATE
    tags: list[str] = Field(default_factory=list, max_length=50)
    source: str = Field(default="manual", min_length=1, max_length=200)
    importance: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=1.0, ge=0, le=1)
    related_memory_ids: list[UUID] = Field(default_factory=list, max_length=100)
    human_approved: bool = True
    automatic_external_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "MemoryCreate":
        if self.automatic_external_action:
            raise ValueError("automatic external actions are disabled")
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class MemoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=20000)
    memory_type: MemoryType | None = None
    visibility: MemoryVisibility | None = None
    tags: list[str] | None = Field(default=None, max_length=50)
    importance: float | None = Field(default=None, ge=0, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    related_memory_ids: list[UUID] | None = Field(default=None, max_length=100)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_approval(self) -> "MemoryUpdate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class MemoryRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    title: str
    content: str
    memory_type: MemoryType
    visibility: MemoryVisibility
    state: MemoryState = MemoryState.ACTIVE
    tags: list[str]
    source: str
    importance: float
    confidence: float
    related_memory_ids: list[UUID]
    access_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed_at: datetime | None = None


class MemoryQuery(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    query: str = Field(min_length=1, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    memory_types: list[MemoryType] = Field(default_factory=list, max_length=10)
    include_archived: bool = False
    limit: int = Field(default=10, ge=1, le=100)


class MemorySearchResult(BaseModel):
    memory: MemoryRecord
    relevance_score: float
    matched_terms: list[str]


class MemoryStateChange(BaseModel):
    human_approved: bool = True
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_approval(self) -> "MemoryStateChange":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class MemoryEngineStatus(BaseModel):
    service: str = "memory-engine"
    version: str = "7.7"
    total_memories: int
    active_memories: int
    archived_memories: int
    deleted_memories: int
    workspace_isolation_enabled: bool = True
    configurable_ownership: bool = True
    automatic_external_actions: bool = False
    human_approval_required_for_mutation: bool = True
