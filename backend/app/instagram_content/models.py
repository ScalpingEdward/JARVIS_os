from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ContentStatus(StrEnum):
    proposed = "proposed"
    moderation_rejected = "moderation_rejected"
    approved = "approved"
    rejected = "rejected"
    posted = "posted"
    post_failed = "post_failed"


class MediaType(StrEnum):
    image = "image"
    video = "video"


class PostFormat(StrEnum):
    single_image = "single_image"
    carousel = "carousel"
    reel = "reel"


class MediaItem(BaseModel):
    """One raw image or video, before any edit has been applied to it."""

    media_ref: str = Field(min_length=1, max_length=2000, description="Google Drive file id or URL")
    media_type: MediaType
    aesthetic_score: float = Field(ge=0, le=1, description="How well this item fits the high-end account aesthetic")
    duration_seconds: float | None = Field(default=None, gt=0, description="Required for video, must be omitted for image")

    @model_validator(mode="after")
    def _duration_matches_type(self) -> "MediaItem":
        if self.media_type == MediaType.video and self.duration_seconds is None:
            raise ValueError("duration_seconds is required for video media items")
        if self.media_type == MediaType.image and self.duration_seconds is not None:
            raise ValueError("duration_seconds must not be set for image media items")
        return self


class EditInstruction(BaseModel):
    """What should happen to one media item before it's posted -- a
    specification for n8n (or whatever executes real pixel/video work) to
    carry out, not the edit itself. AURON does not have file access to Drive
    and does not perform real image/video processing."""

    media_ref: str
    target_aspect_ratio: str
    color_grade_preset: str
    target_duration_seconds: tuple[float, float] | None = Field(
        default=None, description="(min, max) recommended duration in seconds, video only."
    )
    trim_needed: bool = False
    trim_start_seconds: float | None = Field(
        default=None, description="Not set by AURON -- selecting the actual best segment needs human/real video analysis."
    )
    trim_end_seconds: float | None = None
    notes: str = ""


class ContentCandidateCreate(BaseModel):
    """A single proposed post, before any human has seen it. One or more
    media items: one video -> reel, one image -> single post, 2-10 items
    (image and/or video mixed) -> carousel, matching Instagram's own rules."""

    media_items: list[MediaItem] = Field(min_length=1, max_length=10)
    caption_draft: str = Field(min_length=1, max_length=2200)
    aesthetic_notes: str = Field(default="", max_length=2000)


class ContentDecision(BaseModel):
    approved: bool
    reason: str = Field(min_length=1, max_length=2000)
    edited_caption: str | None = Field(default=None, max_length=2200)


class ContentCandidate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    media_items: list[MediaItem]
    post_format: PostFormat
    format_reasoning: str
    edit_plan: list[EditInstruction] = Field(default_factory=list)
    caption_draft: str
    aesthetic_notes: str = ""
    status: ContentStatus = ContentStatus.proposed
    decision_reason: str | None = None
    moderation_warnings: list[str] = Field(default_factory=list)
    hook_warnings: list[str] = Field(default_factory=list)
    published_media_id: str | None = None
    audit_log: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContentCandidateList(BaseModel):
    items: list[ContentCandidate]
    count: int
