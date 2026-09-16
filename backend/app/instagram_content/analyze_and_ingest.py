from __future__ import annotations

import base64
from datetime import datetime
from io import BytesIO

from PIL import Image

from .analysis_completeness import analysis_is_complete
from .media_pool_models import (
    MediaAnalyzeAndIngestItem,
    MediaAnalyzeAndIngestItemResult,
    MediaAnalyzeAndIngestResponse,
    MediaPoolIngestRequest,
    MediaPoolItemCreate,
)
from .media_pool_service import MediaPoolService
from .models import MediaType
from .vision_analysis import AnthropicVisionAnalyzer, VisionAnalysisError

_EXIF_IFD_EXIF = 0x8769
_TAG_DATETIME_ORIGINAL = 0x9003
_TAG_OFFSET_TIME_ORIGINAL = 0x9011

#: Videos have no frame-extraction step yet (see the n8n ingest workflow's own
#: note on this), so there is no image for Claude to look at. curate() never
#: gates videos on aesthetic_score -- they always become a standalone Reel
#: regardless of score (see curation.py) -- so this placeholder only affects
#: ranking within a single curate() call, never whether a video gets proposed
#: at all.
_VIDEO_PLACEHOLDER_AESTHETIC_SCORE = 0.6

_DOWNSCALE_THRESHOLD_BYTES = 4 * 1024 * 1024
_MAX_EDGE_PX = 2000
_JPEG_QUALITY = 85


def _downscale_if_needed(image_base64: str | None, image_media_type: str | None) -> tuple[str | None, str | None]:
    """Shrinks oversized images before they reach the Anthropic Vision API,
    which rejects anything over ~10 MB with invalid_request_error. Only
    re-encodes when the decoded bytes exceed 4 MB or the longest edge
    exceeds 2000px; anything already small enough passes through untouched.
    Any failure (corrupt data, unsupported format, ...) falls back to the
    original bytes unchanged -- this is a size optimization, not something
    that should ever block ingest."""
    if not image_base64:
        return image_base64, image_media_type
    try:
        raw = base64.b64decode(image_base64)
        image = Image.open(BytesIO(raw))
        image.load()

        if len(raw) <= _DOWNSCALE_THRESHOLD_BYTES and max(image.size) <= _MAX_EDGE_PX:
            return image_base64, image_media_type

        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        scale = _MAX_EDGE_PX / max(image.size)
        if scale < 1:
            new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
            image = image.resize(new_size, Image.LANCZOS)

        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=_JPEG_QUALITY)
        return base64.b64encode(buffer.getvalue()).decode("ascii"), "image/jpeg"
    except Exception:
        return image_base64, image_media_type


def _read_captured_at(image_base64: str | None) -> datetime | None:
    """Best-effort EXIF DateTimeOriginal extraction, with OffsetTimeOriginal
    applied as the timezone when present. Returns None on any failure --
    missing EXIF, corrupt image data, unexpected format -- ingest must never
    fail just because a photo's capture time couldn't be read."""
    if not image_base64:
        return None
    try:
        image = Image.open(BytesIO(base64.b64decode(image_base64)))
        exif_ifd = image.getexif().get_ifd(_EXIF_IFD_EXIF)
        raw_datetime = exif_ifd.get(_TAG_DATETIME_ORIGINAL)
        if not raw_datetime:
            return None
        naive = datetime.strptime(raw_datetime, "%Y:%m:%d %H:%M:%S")
        raw_offset = exif_ifd.get(_TAG_OFFSET_TIME_ORIGINAL)
        if raw_offset:
            return naive.replace(tzinfo=datetime.strptime(raw_offset, "%z").tzinfo)
        return naive
    except Exception:
        return None


def analyze_and_ingest(
    items: list[MediaAnalyzeAndIngestItem],
    analyzer: AnthropicVisionAnalyzer,
    pool_service: MediaPoolService,
) -> MediaAnalyzeAndIngestResponse:
    """Runs real vision analysis on each item and, for everything that
    succeeds, ingests it into the media pool with the theme/tags/score
    Claude actually derived from looking at the image -- not a guess, and
    not silently skipped: every item's outcome (success or a specific
    failure reason) comes back in the response.
    """
    results: list[MediaAnalyzeAndIngestItemResult] = []
    creates: list[MediaPoolItemCreate] = []
    # Only a *real* analysis blocks re-processing. An item that was ingested
    # with placeholders (a video with no frame to look at, say) stays eligible,
    # otherwise it would keep its empty analysis forever: the pre-filter in the
    # n8n workflow would drop it as "known" on every run and nothing would ever
    # revisit it. pool_service.ingest() then updates that row in place instead
    # of inserting a duplicate.
    analyzed_media_refs = {
        existing.media_ref for existing in pool_service.list_all() if analysis_is_complete(existing)
    }

    for item in items:
        if item.media_ref in analyzed_media_refs:
            results.append(
                MediaAnalyzeAndIngestItemResult(
                    media_ref=item.media_ref,
                    success=True,
                    reasoning="Already in the media pool with a real analysis -- skipped vision analysis.",
                )
            )
            continue

        if item.media_type == MediaType.video and item.duration_seconds is None:
            results.append(
                MediaAnalyzeAndIngestItemResult(
                    media_ref=item.media_ref, success=False, error="duration_seconds is required for video items"
                )
            )
            continue

        if item.media_type == MediaType.video and not item.image_base64 and not item.image_url:
            theme = item.captured_at.date().isoformat() if item.captured_at else "video"
            creates.append(
                MediaPoolItemCreate(
                    media_ref=item.media_ref,
                    media_type=item.media_type,
                    theme=theme,
                    tags=[],
                    aesthetic_score=_VIDEO_PLACEHOLDER_AESTHETIC_SCORE,
                    duration_seconds=item.duration_seconds,
                    source_group=item.source_group,
                    captured_at=item.captured_at,
                )
            )
            results.append(
                MediaAnalyzeAndIngestItemResult(
                    media_ref=item.media_ref,
                    success=True,
                    theme=theme,
                    tags=[],
                    aesthetic_score=_VIDEO_PLACEHOLDER_AESTHETIC_SCORE,
                    reasoning="Video -- no vision analysis (no frame extraction yet), placeholder score used. "
                    "curate() always treats videos as standalone Reels regardless of score.",
                )
            )
            continue

        try:
            scaled_image_base64, scaled_image_media_type = _downscale_if_needed(
                item.image_base64, item.image_media_type
            )
            analysis = analyzer.analyze(
                image_base64=scaled_image_base64, image_media_type=scaled_image_media_type, image_url=item.image_url
            )
        except VisionAnalysisError as exc:
            results.append(MediaAnalyzeAndIngestItemResult(media_ref=item.media_ref, success=False, error=str(exc)))
            continue

        creates.append(
            MediaPoolItemCreate(
                media_ref=item.media_ref,
                media_type=item.media_type,
                theme=analysis.theme,
                tags=analysis.tags,
                aesthetic_score=analysis.aesthetic_score,
                duration_seconds=item.duration_seconds,
                source_group=item.source_group,
                captured_at=item.captured_at or _read_captured_at(item.image_base64),
            )
        )
        results.append(
            MediaAnalyzeAndIngestItemResult(
                media_ref=item.media_ref,
                success=True,
                theme=analysis.theme,
                tags=analysis.tags,
                aesthetic_score=analysis.aesthetic_score,
                reasoning=analysis.reasoning,
            )
        )

    ingested = 0
    if creates:
        ingest_response = pool_service.ingest(MediaPoolIngestRequest(items=creates))
        ingested = ingest_response.ingested

    failed = sum(1 for r in results if not r.success)
    return MediaAnalyzeAndIngestResponse(results=results, analyzed_and_ingested=ingested, failed=failed)
