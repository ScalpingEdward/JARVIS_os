from __future__ import annotations

import base64
from datetime import datetime
from io import BytesIO

from PIL import Image

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
    existing_media_refs = {existing.media_ref for existing in pool_service.list_all()}

    for item in items:
        if item.media_ref in existing_media_refs:
            results.append(
                MediaAnalyzeAndIngestItemResult(
                    media_ref=item.media_ref,
                    success=True,
                    reasoning="Already in the media pool -- skipped vision analysis.",
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

        try:
            analysis = analyzer.analyze(
                image_base64=item.image_base64, image_media_type=item.image_media_type, image_url=item.image_url
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
