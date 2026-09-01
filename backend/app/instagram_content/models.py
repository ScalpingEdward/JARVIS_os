from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ContentStatus(StrEnum):
    proposed = "proposed"
    moderation_rejected = "moderation_rejected"
    approved = "approved"
    rejected = "rejected"
    posted = "posted"
    post_failed = "post_failed"


class ContentCandidateCreate(BaseModel):
    """A single proposed post, before any human has seen it."""

    image_source_ref: str = Field(min_length=1, max_length=2000, description="Google Drive file id or URL")
    caption_draft: str = Field(min_length=1, max_length=2200)
    aesthetic_score: float = Field(ge=0, le=1, description="How well the image fits the high-end account aesthetic")
    aesthetic_notes: str = Field(default="", max_length=2000)


class ContentDecision(BaseModel):
    approved: bool
    reason: str = Field(min_length=1, max_length=2000)
    edited_caption: str | None = Field(default=None, max_length=2200)


class ContentCandidate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    image_source_ref: str
    caption_draft: str
    aesthetic_score: float
    aesthetic_notes: str = ""
    status: ContentStatus = ContentStatus.proposed
    decision_reason: str | None = None
    moderation_warnings: list[str] = Field(default_factory=list)
    published_media_id: str | None = None
    audit_log: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContentCandidateList(BaseModel):
    items: list[ContentCandidate]
    count: int
