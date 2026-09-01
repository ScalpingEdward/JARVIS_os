from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from .models import MediaType


class MediaPoolItemCreate(BaseModel):
    """One analyzed photo or video from the source folder (Drive), ready to
    be considered for a post. AURON does not analyze pixels itself -- theme,
    tags, and aesthetic_score come from whatever vision-analysis step runs
    where the files actually live (n8n, or a script with Drive access)."""

    media_ref: str = Field(min_length=1, max_length=2000, description="Google Drive file id or URL")
    media_type: MediaType
    theme: str = Field(
        min_length=1,
        max_length=100,
        description="A short, consistent theme label, e.g. 'gold-trading-desk', 'mystic-symbol', 'quote-card'. "
        "Items only get grouped into the same carousel if their theme matches.",
    )
    tags: list[str] = Field(default_factory=list, max_length=20)
    aesthetic_score: float = Field(ge=0, le=1)
    duration_seconds: float | None = Field(default=None, gt=0)
    dominant_color_hex: str | None = Field(default=None, max_length=7)
    recommended_trim_start_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Real, analyzed trim window (video only) -- set by video_trim_analysis.py from actual "
        "sampled frames, never invented. None means no trim analysis has run for this item yet.",
    )
    recommended_trim_end_seconds: float | None = Field(default=None, gt=0)
    trim_reasoning: str = Field(default="", max_length=1000)
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _duration_matches_type(self) -> "MediaPoolItemCreate":
        if self.media_type == MediaType.video and self.duration_seconds is None:
            raise ValueError("duration_seconds is required for video media items")
        if self.media_type == MediaType.image and self.duration_seconds is not None:
            raise ValueError("duration_seconds must not be set for image media items")
        return self


class MediaPoolItem(MediaPoolItemCreate):
    id: UUID = Field(default_factory=uuid4)
    used: bool = False
    used_in_candidate_id: UUID | None = None
    used_at: datetime | None = None
    reserved_in_draft_id: UUID | None = None

    @property
    def available(self) -> bool:
        return not self.used and self.reserved_in_draft_id is None


class MediaPoolIngestRequest(BaseModel):
    items: list[MediaPoolItemCreate] = Field(min_length=1, max_length=500)


class MediaPoolIngestResponse(BaseModel):
    ingested: int
    skipped_duplicates: int
    pool_size_unused: int


class MediaPoolList(BaseModel):
    items: list[MediaPoolItem]
    count: int


class CuratedDraft(BaseModel):
    """One curated grouping (hero post, or right-sized carousel/reel),
    reserved out of the pool but not yet a real candidate -- still needs a
    caption before it can be finalized. Reserving (rather than immediately
    consuming) means two curation runs never propose the same photo twice,
    while a discarded draft cleanly returns its items to the pool."""

    id: UUID = Field(default_factory=uuid4)
    theme: str
    reasoning: str
    media_item_ids: list[UUID]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finalized: bool = False
    finalized_candidate_id: UUID | None = None
    discarded: bool = False


class CuratedDraftList(BaseModel):
    items: list[CuratedDraft]
    count: int


class FinalizeDraftRequest(BaseModel):
    caption_draft: str | None = Field(
        default=None,
        max_length=2200,
        description="If omitted, AURON generates one itself via a real Anthropic API call (needs ANTHROPIC_API_KEY set).",
    )
    aesthetic_notes: str = Field(default="", max_length=2000)


class MediaAnalyzeAndIngestItem(BaseModel):
    """One raw media reference to analyze and, on success, add to the pool.
    AURON never fetches the file itself -- the caller supplies the bytes
    or an already-fetchable URL. For video, this must be a representative
    still frame (a thumbnail), not the video itself: Claude's vision
    analyzes a single image, not motion/audio."""

    media_ref: str = Field(min_length=1, max_length=2000)
    media_type: MediaType
    image_base64: str | None = Field(default=None, description="Base64-encoded image bytes (the photo, or a video thumbnail).")
    image_media_type: str | None = Field(default=None, description="e.g. 'image/jpeg', required together with image_base64.")
    image_url: str | None = Field(default=None, description="Alternative to image_base64: an already-fetchable image URL.")
    duration_seconds: float | None = Field(default=None, gt=0, description="Required for video; ignored for image.")


class MediaAnalyzeAndIngestRequest(BaseModel):
    items: list[MediaAnalyzeAndIngestItem] = Field(min_length=1, max_length=50)


class MediaAnalyzeAndIngestItemResult(BaseModel):
    media_ref: str
    success: bool
    theme: str | None = None
    tags: list[str] = Field(default_factory=list)
    aesthetic_score: float | None = None
    reasoning: str | None = None
    error: str | None = None


class MediaAnalyzeAndIngestResponse(BaseModel):
    results: list[MediaAnalyzeAndIngestItemResult]
    analyzed_and_ingested: int
    failed: int


class FrameSample(BaseModel):
    """One sampled still frame from a video, at a known timestamp. AURON
    never receives or processes the video itself -- the caller (n8n, or a
    script with Drive access) extracts frames at a regular interval and
    supplies them here."""

    timestamp_seconds: float = Field(ge=0)
    image_base64: str | None = None
    image_media_type: str | None = None
    image_url: str | None = None


class TrimAnalysisRequest(BaseModel):
    frames: list[FrameSample] = Field(
        min_length=3,
        max_length=30,
        description="Sampled frames across the video's full length, ideally at a regular interval.",
    )
    target_min_seconds: float = Field(default=15.0, gt=0)
    target_max_seconds: float = Field(default=30.0, gt=0)


class TrimAnalysisResult(BaseModel):
    recommended_start_seconds: float
    recommended_end_seconds: float
    reasoning: str
