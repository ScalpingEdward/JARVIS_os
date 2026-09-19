from __future__ import annotations

import base64
import logging
import os
from datetime import datetime
from io import BytesIO

from PIL import Image

from .analysis_completeness import analysis_is_complete
from .captured_at_resolution import resolve_captured_at
from .ingest_paths import IngestPathError, ingest_directory_status, resolve_ingest_path
from .media_pool_models import (
    MediaAnalyzeAndIngestItem,
    MediaAnalyzeAndIngestItemResult,
    MediaAnalyzeAndIngestResponse,
    MediaPoolIngestRequest,
    MediaPoolItemCreate,
    TrimAnalysisResult,
)
from .media_processing import MediaProcessingError, process_video
from .media_pool_service import MediaPoolService
from .models import MediaType
from .reel_targets import needs_trim, target_max_seconds, target_min_seconds
from .video_frame_extraction import (
    VideoFrameExtractionError,
    probe_creation_time,
    representative_frame,
    sample_video,
)
from .video_trim_analysis import (
    AnthropicVideoTrimAnalyzer,
    VideoTrimAnalysisConfig,
    VideoTrimAnalysisError,
)
from .vision_analysis import AnthropicVisionAnalyzer, VisionAnalysisError

logger = logging.getLogger(__name__)

_EXIF_IFD_EXIF = 0x8769
_TAG_DATETIME_ORIGINAL = 0x9003
_TAG_OFFSET_TIME_ORIGINAL = 0x9011

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


def _size_mismatch(video_path, expected_size_bytes: int | None) -> str | None:
    """Compares the handed-over file against the size Drive itself reports.

    A write that was cut short leaves a partial file, and nothing renames it
    into place afterwards -- the ReadWriteFile node cannot. Detecting that
    from the file's own contents does not work reliably: an MP4 written with
    +faststart, which is what phones produce, keeps its moov atom at the
    front, so ffprobe reads the full original duration off a half file and
    reports it with total confidence. Frame extraction catches the blatant
    cases, but measured against real truncations it only bites from roughly
    5% missing; a file short by its last one to three percent passes with a
    duration that is simply wrong.

    So this compares two numbers instead of judging how broken something
    looks. It runs before ffprobe is ever invoked.
    """
    if expected_size_bytes is None:
        return None
    try:
        actual = video_path.stat().st_size
    except OSError as exc:
        return f"cannot stat {video_path.name}: {exc}"
    if actual != expected_size_bytes:
        return (
            f"{video_path.name} is {actual} bytes but Drive reports {expected_size_bytes} "
            f"({actual - expected_size_bytes:+d} on disk) -- the handover was incomplete, "
            f"refusing to analyze a partial file"
        )
    return None


def _trim_window(
    frames: list,
    duration_seconds: float,
    trim_analyzer: "AnthropicVideoTrimAnalyzer | None",
    media_ref: str,
) -> "TrimAnalysisResult | None":
    """A real trim window, but only for a video that is actually too long.

    What counts as too long is a content-strategy decision, so it comes from
    configuration rather than a constant here. For anything already inside
    the target range there is nothing to cut and no reason to spend a call.

    Reuses the frames that were sampled for the analysis -- this is the only
    moment they exist, since the file is gone once the ingest succeeds. A
    failure here is not fatal: the item still gets its analysis and its
    cover, just no trim recommendation.
    """
    if not needs_trim(duration_seconds):
        return None
    analyzer = trim_analyzer or AnthropicVideoTrimAnalyzer(
        config=VideoTrimAnalysisConfig(api_key=os.getenv("ANTHROPIC_API_KEY"))
    )
    try:
        return analyzer.analyze(frames, target_min_seconds(), target_max_seconds())
    except VideoTrimAnalysisError as exc:
        logger.warning("trim analysis failed for %s, continuing without one: %s", media_ref, exc)
        return None


def _choose_cover_timestamp(analysis, trim: "TrimAnalysisResult | None", frames: list) -> float:
    """Which frame becomes the Reel cover.

    Never returns None for a video that got this far, deliberately: the
    Graph API defaults thumb_offset to 0, and frame 0 of phone footage is
    regularly black, blurred or mid-movement -- the single worst candidate
    for the image that decides whether anyone watches.

    1. what the vision model picked, seeing every frame at once
    2. the start of the trim window -- where the Reel actually begins
    3. the middle sampled frame: unremarkable, but never the opening one
    """
    if analysis.cover_timestamp_seconds is not None:
        return analysis.cover_timestamp_seconds
    if trim is not None:
        return trim.recommended_start_seconds
    return representative_frame(frames).timestamp_seconds


def _process_now(
    video_path,
    *,
    media_ref: str,
    trim: "TrimAnalysisResult | None",
    duration_seconds: float,
) -> str | None:
    """Cut and grade the clip while the file is still here.

    This is the only moment it can happen: the handed-over original lives in
    the ingest directory, which the sweeper empties within a day, and a
    draft may sit waiting for a decision far longer than that. What comes
    out of here survives in the processed directory and is what actually
    gets posted.

    Deliberately no crop yet. The aspect ratio depends on whether the item
    ends up a Reel or a slide in a carousel, and that is decided later by
    curation -- cropping to a guess now would mean re-cropping an already
    cropped file, losing pixels twice.

    Not fatal on failure: the analysis is real and worth keeping either way,
    and the result says plainly that nothing was processed rather than
    pretending the original is ready to post.
    """
    try:
        processed = process_video(
            video_path,
            ratio=None,
            trim_start_seconds=trim.recommended_start_seconds if trim else None,
            trim_end_seconds=trim.recommended_end_seconds if trim else None,
            output_name=f"{media_ref}.mp4",
        )
    except MediaProcessingError as exc:
        logger.warning("could not process %s, keeping the analysis without it: %s", media_ref, exc)
        return None
    logger.info(
        "processed %s: %s%s",
        media_ref,
        "graded" if processed.graded else "ungraded (no LUT configured)",
        f", cut to {trim.recommended_start_seconds:.1f}-{trim.recommended_end_seconds:.1f}s"
        if trim else f", full {duration_seconds:.1f}s",
    )
    return processed.path.name


def _trim_note(trim: "TrimAnalysisResult | None") -> str:
    if trim is None:
        return ""
    return f", trim {trim.recommended_start_seconds:.1f}-{trim.recommended_end_seconds:.1f}s"


def analyze_and_ingest(
    items: list[MediaAnalyzeAndIngestItem],
    analyzer: AnthropicVisionAnalyzer,
    pool_service: MediaPoolService,
    trim_analyzer: AnthropicVideoTrimAnalyzer | None = None,
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

        resolved_video_path = None
        if item.video_path is not None:
            # Validated here, at the edge, rather than deep inside the frame
            # extraction that consumes it: a bad or out-of-bounds path fails
            # this one item with a clear reason instead of surfacing as an
            # ffmpeg error, and never reaches the filesystem.
            try:
                resolved_video_path = resolve_ingest_path(item.video_path)
            except IngestPathError as exc:
                results.append(
                    MediaAnalyzeAndIngestItemResult(media_ref=item.media_ref, success=False, error=str(exc))
                )
                continue

        if item.media_type == MediaType.video and resolved_video_path is not None:
            # The frames are sampled exactly once here and then handed to
            # everything that needs them -- the vision analysis, the cover
            # choice, and the trim window. Extracting them per step would be
            # slower and, worse, would drift apart the moment anyone changed
            # the sampling parameters: the cover would sit on a frame the
            # analysis never saw. This is also the only chance to do it at
            # all -- n8n deletes the file once the ingest succeeds.
            #
            # No duration_seconds check here: ffprobe reads the real one out
            # of the file and that wins over whatever the caller sent (a
            # mismatch is logged, never silently reconciled).
            mismatch = _size_mismatch(resolved_video_path, item.expected_size_bytes)
            if mismatch is not None:
                results.append(
                    MediaAnalyzeAndIngestItemResult(media_ref=item.media_ref, success=False, error=mismatch)
                )
                continue

            try:
                duration_seconds, frames = sample_video(
                    resolved_video_path, claimed_duration_seconds=item.duration_seconds
                )
                analysis = analyzer.analyze(frames=frames)
            except (VideoFrameExtractionError, VisionAnalysisError) as exc:
                results.append(
                    MediaAnalyzeAndIngestItemResult(media_ref=item.media_ref, success=False, error=str(exc))
                )
                continue

            trim = _trim_window(frames, duration_seconds, trim_analyzer, item.media_ref)
            cover_timestamp = _choose_cover_timestamp(analysis, trim, frames)

            # Only a video's name is read for a date, and only as the top
            # source. Photos carry real EXIF and need no help; letting a name
            # override that would put a typo above a fact. A video has no EXIF
            # at all, and its container timestamp is whatever the last tool to
            # write the file felt like -- for those, the name is the only
            # statement a human can make that survives an export.
            captured_at, captured_at_source = resolve_captured_at(
                file_name=item.file_name,
                exif=item.captured_at,
                video_creation_time=item.video_creation_time or probe_creation_time(resolved_video_path),
                upload_time=item.upload_time,
            )
            processed_file = _process_now(
                resolved_video_path,
                media_ref=item.media_ref,
                trim=trim,
                duration_seconds=duration_seconds,
            )
            creates.append(
                MediaPoolItemCreate(
                    media_ref=item.media_ref,
                    media_type=item.media_type,
                    theme=analysis.theme,
                    tags=analysis.tags,
                    aesthetic_score=analysis.aesthetic_score,
                    duration_seconds=duration_seconds,
                    source_group=item.source_group,
                    captured_at=captured_at,
                    captured_at_source=captured_at_source,
                    cover_timestamp_seconds=cover_timestamp,
                    processed_file=processed_file,
                    recommended_trim_start_seconds=trim.recommended_start_seconds if trim else None,
                    recommended_trim_end_seconds=trim.recommended_end_seconds if trim else None,
                    trim_reasoning=trim.reasoning if trim else "",
                )
            )
            results.append(
                MediaAnalyzeAndIngestItemResult(
                    media_ref=item.media_ref,
                    success=True,
                    theme=analysis.theme,
                    tags=analysis.tags,
                    aesthetic_score=analysis.aesthetic_score,
                    reasoning=(
                        f"Analyzed {len(frames)} sampled frames "
                        f"({frames[0].timestamp_seconds:.1f}s-{frames[-1].timestamp_seconds:.1f}s "
                        f"of {duration_seconds:.2f}s), cover at {cover_timestamp:.3f}s"
                        f"{_trim_note(trim)}. {analysis.reasoning}"
                    ),
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
            # There is nothing here to analyze: no path to sample frames from
            # and no thumbnail to look at. This used to write a placeholder
            # entry and report success -- a stopgap for the time before frame
            # extraction existed. That time is over, and the stopgap turned
            # into the worst kind of failure: the first real run handed over
            # 29 videos whose video_path had been silently dropped, and every
            # one came back "success" with analyzed_and_ingested 0. Nothing
            # was analyzed, nothing was reported, and the pool looked
            # untouched for a reason nobody could see.
            results.append(
                MediaAnalyzeAndIngestItemResult(
                    media_ref=item.media_ref,
                    success=False,
                    error="video item has neither video_path nor an image to analyze -- "
                    "nothing to derive a theme, tags or a score from. AURON will not write a "
                    "placeholder entry: it would be indistinguishable from a real analysis "
                    "that produced nothing.",
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

        captured_at, captured_at_source = resolve_captured_at(
            # Videos only -- see the same call in the path branch above. This
            # branch serves both kinds: an image (real EXIF, name ignored) and
            # a video handed over as a thumbnail rather than a path.
            file_name=item.file_name if item.media_type == MediaType.video else None,
            exif=item.captured_at or _read_captured_at(item.image_base64),
            video_creation_time=item.video_creation_time,
            upload_time=item.upload_time,
        )
        creates.append(
            MediaPoolItemCreate(
                media_ref=item.media_ref,
                media_type=item.media_type,
                theme=analysis.theme,
                tags=analysis.tags,
                aesthetic_score=analysis.aesthetic_score,
                duration_seconds=item.duration_seconds,
                source_group=item.source_group,
                captured_at=captured_at,
                captured_at_source=captured_at_source,
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

    _report_ingest_directory()

    failed = sum(1 for r in results if not r.success)
    return MediaAnalyzeAndIngestResponse(results=results, analyzed_and_ingested=ingested, failed=failed)


def _report_ingest_directory() -> None:
    """Says what is lying in the handoff directory after every run.

    Removal happens in the ingest-sweeper sidecar, on a timer, with no output
    anyone reads. If that process dies, nothing about it is loud: files would
    simply accumulate until a disk filled. Stating the directory's state on
    every single ingest is what turns that into something visible, and it is
    stated by a container that cannot delete and therefore cannot hide it.
    """
    status = ingest_directory_status()
    if not status.available:
        logger.warning("ingest directory unavailable: %s", status.detail)
        return
    if status.file_count == 0:
        logger.info("ingest directory is empty")
        return
    log = logger.warning if status.stale_files else logger.info
    log(
        "ingest directory holds %d file(s), %.1f MB, oldest %.1fh; %d past the %.0fh retention window%s",
        status.file_count,
        status.total_bytes / 1_048_576,
        status.oldest_age_hours or 0.0,
        len(status.stale_files),
        status.retention_hours,
        f" ({', '.join(f.name for f in status.stale_files[:5])})" if status.stale_files else "",
    )
