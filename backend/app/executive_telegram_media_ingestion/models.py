from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class IngestionState(str, Enum):
    rejected = "rejected"
    quarantined = "quarantined"
    accepted = "accepted"
    vision_ready = "vision-ready"
    dispatched = "dispatched"


class TelegramMediaPolicy(BaseModel):
    allowed_mime_types: list[str] = Field(default_factory=lambda: ["image/jpeg", "image/png", "image/webp"])
    maximum_size_bytes: int = Field(default=12_000_000, gt=0)
    minimum_width: int = Field(default=640, ge=1)
    minimum_height: int = Field(default=360, ge=1)
    require_allowlisted_chat: bool = True
    require_caption_or_chart_context: bool = False
    require_human_approval: bool = False


class TelegramMediaIngestionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    telegram_message_id: str = Field(min_length=1, max_length=120)
    telegram_sender_id: str | None = Field(default=None, max_length=120)
    caption: str | None = Field(default=None, max_length=4000)
    media_reference: str = Field(min_length=1, max_length=500)
    image_sha256: str = Field(min_length=32, max_length=64)
    mime_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    chat_allowlisted: bool = False
    malware_scan_clear: bool = True
    vision_provider_available: bool = True
    human_approved: bool = False
    policy: TelegramMediaPolicy = Field(default_factory=TelegramMediaPolicy)


class IngestionScores(BaseModel):
    source_trust: int = Field(ge=0, le=100)
    media_integrity: int = Field(ge=0, le=100)
    chart_readability: int = Field(ge=0, le=100)
    dispatch_readiness: int = Field(ge=0, le=100)


class TelegramMediaIngestion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    telegram_chat_id: str
    telegram_message_id: str
    media_reference: str
    image_sha256: str
    state: IngestionState
    dispatchable: bool
    target_module: str | None
    recommended_action: str
    scores: IngestionScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IngestionStatusResponse(BaseModel):
    workspace_id: str
    ingestions: int
    latest_state: IngestionState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    ingestion_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
