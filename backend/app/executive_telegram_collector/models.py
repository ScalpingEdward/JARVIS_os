from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TelegramCollectorState(str, Enum):
    blocked = "blocked"
    session_required = "session-required"
    source_rejected = "source-rejected"
    retrieval_queued = "retrieval-queued"
    media_ready = "media-ready"
    dispatched = "dispatched"


class TelegramCollectorPolicy(BaseModel):
    require_isolated_session_reference: bool = True
    require_allowlisted_source: bool = True
    maximum_message_age_seconds: int = Field(default=900, gt=0)
    maximum_media_bytes: int = Field(default=12_000_000, gt=0)
    allowed_mime_types: list[str] = Field(default_factory=lambda: ["image/jpeg", "image/png", "image/webp"])
    maximum_retrieval_attempts: int = Field(default=3, ge=1, le=10)
    require_read_only_client: bool = True


class TelegramCollectorAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    collector_id: str = Field(min_length=1, max_length=100)
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    telegram_message_id: str = Field(min_length=1, max_length=120)
    telegram_sender_id: str | None = Field(default=None, max_length=120)
    session_reference: str | None = Field(default=None, max_length=250)
    session_resolved: bool = False
    session_file_embedded: bool = False
    source_allowlisted: bool = False
    read_only_client: bool = True
    message_age_seconds: int = Field(default=0, ge=0)
    media_present: bool = True
    media_reference: str | None = Field(default=None, max_length=500)
    mime_type: str | None = Field(default=None, max_length=100)
    size_bytes: int = Field(default=0, ge=0)
    width: int = Field(default=0, ge=0)
    height: int = Field(default=0, ge=0)
    retrieval_attempts: int = Field(default=1, ge=1, le=10)
    retrieval_success: bool = False
    retryable_failure: bool = False
    image_sha256: str | None = Field(default=None, min_length=32, max_length=64)
    caption: str | None = Field(default=None, max_length=4000)
    risk_brain_clear: bool = True
    policy: TelegramCollectorPolicy = Field(default_factory=TelegramCollectorPolicy)


class TelegramCollectorScores(BaseModel):
    session_isolation: int = Field(ge=0, le=100)
    source_trust: int = Field(ge=0, le=100)
    freshness: int = Field(ge=0, le=100)
    media_integrity: int = Field(ge=0, le=100)
    retrieval_reliability: int = Field(ge=0, le=100)
    collector_confidence: int = Field(ge=0, le=100)


class TelegramCollectorAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    collector_id: str
    telegram_chat_id: str
    telegram_message_id: str
    state: TelegramCollectorState
    dispatchable: bool
    target_module: str | None
    media_reference: str | None
    image_sha256: str | None
    recommended_action: str
    scores: TelegramCollectorScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TelegramCollectorStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: TelegramCollectorState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
