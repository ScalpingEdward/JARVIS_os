from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class DocumentState(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class SourceType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "markdown"
    CSV = "csv"
    JSON = "json"
    WEB = "web"
    NOTE = "note"
    MANUAL = "manual"


class TrustLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERIFIED = "verified"


class CollectionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_approval(self) -> "CollectionCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class CollectionRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    key: str
    name: str
    description: str
    document_count: int = 0
    chunk_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DocumentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    collection_id: UUID
    title: str = Field(min_length=1, max_length=300)
    source_type: SourceType
    source_uri: str | None = Field(default=None, max_length=2000)
    author: str = Field(default="", max_length=300)
    version: str = Field(default="1", min_length=1, max_length=80)
    content: str = Field(default="", max_length=2_000_000)
    tags: list[str] = Field(default_factory=list, max_length=100)
    trust_level: TrustLevel = TrustLevel.MEDIUM
    priority: int = Field(default=50, ge=0, le=100)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_cloud_upload: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "DocumentCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_cloud_upload:
            raise ValueError("automatic cloud uploads are disabled")
        return self


class DocumentRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    collection_id: UUID
    title: str
    source_type: SourceType
    source_uri: str | None
    author: str
    version: str
    content: str
    tags: list[str]
    trust_level: TrustLevel
    priority: int
    metadata: dict[str, Any]
    state: DocumentState = DocumentState.ACTIVE
    content_hash: str
    chunk_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    archived_at: datetime | None = None


class ChunkCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    document_id: UUID
    text: str = Field(min_length=1, max_length=100_000)
    ordinal: int = Field(ge=0)
    section: str = Field(default="", max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = Field(default=None, max_length=8192)
    embedding_model: str | None = Field(default=None, max_length=160)
    human_approved: bool = True
    external_embedding_request: bool = False

    @model_validator(mode="after")
    def enforce_embedding_safety(self) -> "ChunkCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.external_embedding_request:
            raise ValueError("automatic external embedding requests are disabled")
        return self


class ChunkRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    document_id: UUID
    text: str
    ordinal: int
    section: str
    metadata: dict[str, Any]
    embedding: list[float] | None
    embedding_model: str | None
    token_estimate: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SearchMode(str, Enum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class SearchRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    query: str = Field(min_length=1, max_length=5000)
    collection_ids: list[UUID] = Field(default_factory=list, max_length=100)
    mode: SearchMode = SearchMode.HYBRID
    query_embedding: list[float] | None = Field(default=None, max_length=8192)
    tags: list[str] = Field(default_factory=list, max_length=100)
    minimum_trust: TrustLevel | None = None
    include_archived: bool = False
    limit: int = Field(default=10, ge=1, le=100)
    human_approved: bool = True
    external_embedding_request: bool = False

    @model_validator(mode="after")
    def enforce_search_safety(self) -> "SearchRequest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.external_embedding_request:
            raise ValueError("automatic external embedding requests are disabled")
        if self.mode == SearchMode.SEMANTIC and self.query_embedding is None:
            raise ValueError("semantic search requires a supplied query embedding")
        return self


class SearchHit(BaseModel):
    chunk_id: UUID
    document_id: UUID
    collection_id: UUID
    title: str
    text: str
    section: str
    score: float
    keyword_score: float
    semantic_score: float
    trust_level: TrustLevel
    priority: int
    source_uri: str | None


class SearchRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    requester_id: str
    query: str
    mode: SearchMode
    hits: list[SearchHit]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DocumentMutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    human_approved: bool = True
    reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def require_approval(self) -> "DocumentMutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class EmbeddingRebuildRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    collection_id: UUID | None = None
    model_key: str = Field(default="local-placeholder", min_length=1, max_length=160)
    dry_run: bool = True
    human_approved: bool = True
    execute_external_requests: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "EmbeddingRebuildRequest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if not self.dry_run or self.execute_external_requests:
            raise ValueError("v8.2 only permits dry-run embedding rebuilds")
        return self


class EmbeddingRebuildRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    collection_id: UUID | None
    model_key: str
    candidate_chunks: int
    dry_run: bool = True
    external_requests_executed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    target_type: str
    target_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeEngineStatus(BaseModel):
    service: str = "knowledge-engine"
    version: str = "8.2"
    collections: int
    active_documents: int
    archived_documents: int
    chunks: int
    searches: int
    embedding_rebuild_plans: int
    external_embedding_execution: bool = False
    automatic_cloud_uploads: bool = False
    workspace_isolation: bool = True
    audit_enabled: bool = True
