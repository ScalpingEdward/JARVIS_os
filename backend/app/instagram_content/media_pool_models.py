from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field, model_validator

from .analysis_completeness import analysis_is_complete
from .captured_at_resolution import CapturedAtSource
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
    source_group: str | None = Field(
        default=None,
        max_length=200,
        description="The Drive subfolder the file came from, e.g. 'tag 1'. When set, it takes "
        "precedence over theme for carousel grouping: one folder is one shoot, so its items "
        "belong together regardless of how finely the vision step labelled each theme.",
    )
    captured_at: datetime | None = Field(
        default=None,
        description="When this was actually shot. Used for chronological grouping and sorting. "
        "Always read together with captured_at_source -- a fallback value can be an upload "
        "time rather than a capture time.",
    )
    captured_at_source: CapturedAtSource | None = Field(
        default=None,
        description="Which source captured_at came from: EXIF, the video container's own "
        "creation_time, or -- weakest -- the Drive upload time. None exactly when captured_at "
        "is None. Kept as its own field so an upload time can never masquerade as a capture time.",
    )
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
    cover_timestamp_seconds: float | None = Field(
        default=None,
        gt=0,
        description="Video only: which frame becomes the Reel cover, sent to the Graph API as "
        "thumb_offset (milliseconds). Never None for a video that went through frame extraction -- "
        "the default thumb_offset is 0, i.e. the opening frame, which on phone footage is "
        "regularly black or blurred.",
    )
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _cover_belongs_to_a_video_and_lands_inside_it(self) -> "MediaPoolItemCreate":
        if self.cover_timestamp_seconds is None:
            return self
        if self.media_type != MediaType.video:
            raise ValueError("cover_timestamp_seconds is only meaningful for video media items")
        if self.duration_seconds is not None and self.cover_timestamp_seconds > self.duration_seconds:
            raise ValueError(
                f"cover_timestamp_seconds ({self.cover_timestamp_seconds}s) is past the end of the "
                f"video ({self.duration_seconds}s)"
            )
        return self

    @model_validator(mode="after")
    def _captured_at_carries_its_source(self) -> "MediaPoolItemCreate":
        if (self.captured_at is None) != (self.captured_at_source is None):
            raise ValueError("captured_at and captured_at_source must be set or unset together")
        return self

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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def analysis_complete(self) -> bool:
        """Whether this item carries a real analysis or only placeholders.
        Exposed on /v1/instagram/media-pool so the n8n ingest workflow can
        re-feed incomplete items without re-deriving the rule itself --
        see analysis_completeness.py, the single definition."""
        return analysis_is_complete(self)


class IngestDirectoryFile(BaseModel):
    """One file sitting in the handoff directory right now."""

    name: str
    size_bytes: int
    age_hours: float
    stale: bool = Field(
        description="Older than the retention window, i.e. the ingest-sweeper should already have "
        "removed it. Evidence that the sweeper has stopped, not that an ingest failed."
    )


class IngestDirectoryStatus(BaseModel):
    """What is lying in the video handoff directory.

    Removal is time-based and belongs to the ingest-sweeper sidecar alone:
    n8n writes and never deletes, AURON reads and never deletes. A file
    younger than the retention window is therefore unremarkable.

    A file older than it is not. It means the sweeper has stopped, and this
    report -- written on every ingest and available on demand -- is how that
    becomes visible instead of quietly filling a disk. Monitoring of the
    sweeper, by a container that has no way to delete anything itself.
    """

    file_count: int
    total_bytes: int
    oldest_age_hours: float | None = Field(default=None, description="None when the directory is empty.")
    retention_hours: float
    stale_files: list[IngestDirectoryFile] = Field(default_factory=list)
    available: bool = Field(default=True, description="False when the directory is not mounted or unreadable.")
    detail: str = ""


class MediaPoolIngestRequest(BaseModel):
    items: list[MediaPoolItemCreate] = Field(min_length=1, max_length=500)


class ThemeGap(BaseModel):
    """A theme with too few available items to become a post on its own --
    curate() deliberately leaves these unposted (see curation.py) rather than
    forcing a thin carousel. This surfaces that silent state so a human knows
    what to go shoot, instead of the photos just sitting there unexplained."""

    theme: str
    available_count: int
    needed_for_carousel: int = Field(description="How many more same-theme items would complete a real carousel")
    sample_tags: list[str] = Field(default_factory=list, description="Tags from the existing item(s), as a style hint")
    sample_media_refs: list[str] = Field(default_factory=list)


class ContentGapReport(BaseModel):
    """Read-only. Changes nothing -- purely tells Brano what the pool is
    missing so he can go shoot the right thing, or knows when it's simply
    time to refill the folder."""

    available_count: int
    theme_gaps: list[ThemeGap]
    pool_low: bool = Field(description="True when available_count is at or below the configured low-water mark")
    low_water_mark: int


class MediaPoolIngestResponse(BaseModel):
    ingested: int
    skipped_duplicates: int
    pool_size_unused: int
    updated_incomplete: int = Field(
        default=0,
        description="Known media_refs whose placeholder analysis was replaced by a real one, "
        "rather than being skipped as duplicates.",
    )


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
    source_group: str | None = Field(default=None, max_length=200, description="Drive subfolder name, e.g. 'tag 1'.")
    captured_at: datetime | None = Field(
        default=None,
        description="EXIF capture timestamp, when the caller already knows it. Left unset, "
        "AURON reads it from the image's own EXIF.",
    )
    video_path: str | None = Field(
        default=None,
        max_length=1000,
        description="Path to the downloaded video inside AURON's read-only ingest directory, "
        "relative to it ('1abc.mp4') or absolute within it. The caller (n8n) writes the file "
        "there and passes the path instead of megabytes of base64. Validated against the ingest "
        "root before anything is opened: traversal, symlinks leading out, non-files and "
        "unexpected extensions are refused.",
    )
    video_creation_time: datetime | None = Field(
        default=None,
        description="The video container's own creation_time (MP4 mvhd). Videos carry no EXIF, "
        "so this is the only source that describes when the recording was actually made. "
        "A zeroed field decodes to 1904 and is rejected as implausible, not stored.",
    )
    upload_time: datetime | None = Field(
        default=None,
        description="Google Drive createdTime -- when the file arrived, not when it was shot. "
        "Last-resort fallback; stored only with captured_at_source='upload_time' so it stays "
        "distinguishable from a real capture time.",
    )


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
