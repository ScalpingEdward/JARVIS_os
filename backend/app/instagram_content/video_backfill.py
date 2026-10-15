"""Cutting and grading the videos that entered the pool before any of that
existed.

Thirty of them were analyzed back when ingest only wrote an entry, and four
more died mid-ffmpeg when the container ran out of memory. Their originals
are long gone from the ingest directory (the sweeper empties it within a
day), so each one is fetched back from Drive through n8n, processed exactly
like a new video, and recorded.

No trim: none of these carries an analyzed trim window, and inventing one
here would be a guess about which seconds are the good ones. They are all
under a minute, so the full clip is an honest Reel. A real trim window can
be added later by the analysis that is allowed to decide it.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import httpx

from .drive_fetch import DriveFetchError, fetch_drive_file
from .media_pool_models import MediaPoolItem
from .media_processing import MediaProcessingError, output_dir, process_video
from .media_pool_service import media_pool_service
from .models import MediaType

logger = logging.getLogger(__name__)

#: A phone's 4K clip can be hundreds of MB, and this one goes to disk
#: rather than into a JSON payload, so the cap is about what the laptop can
#: hold and process rather than about a protocol limit.
MAX_VIDEO_BYTES = 600 * 1024 * 1024


def unprocessed_videos() -> list[MediaPoolItem]:
    return [
        item for item in media_pool_service.list_all()
        if item.media_type == MediaType.video and not item.processed_file
    ]


def process_existing_videos(limit: int = 3, offset: int = 0, client: httpx.Client | None = None) -> dict:
    """Fetch, cut and grade up to `limit` of them. A bounded batch on
    purpose: each video is a download plus a full re-encode, and a batch
    that fails halfway has still saved its work.

    `offset` skips past the ones that already failed: without it every call
    starts at the same head of the queue, and one stubborn clip means the
    whole backlog is retried instead of worked through -- two hours of
    re-encoding the same three files.
    """
    todo = sorted(unprocessed_videos(), key=lambda item: item.media_ref)
    batch = todo[offset:offset + limit]
    processed: list[str] = []
    failed: dict[str, str] = {}
    own_client = client is None
    client = client or httpx.Client()
    try:
        for item in batch:
            try:
                data = fetch_drive_file(client, item.media_ref, max_bytes=MAX_VIDEO_BYTES)
            except DriveFetchError as exc:
                failed[item.media_ref] = str(exc)
                continue
            # Written to the processed directory, not /tmp: the container's
            # writable volume is here, and a 400 MB clip in a tmpfs would be
            # 400 MB of the memory that ffmpeg is about to need.
            handle = tempfile.NamedTemporaryFile(dir=output_dir(), suffix=".src.mp4", delete=False)
            source = Path(handle.name)
            try:
                handle.write(data)
                handle.close()
                result = process_video(source, ratio=None, output_name=f"{item.media_ref}.mp4")
            except MediaProcessingError as exc:
                logger.warning("could not process %s: %s", item.media_ref, exc)
                failed[item.media_ref] = str(exc)
                continue
            finally:
                source.unlink(missing_ok=True)
            media_pool_service.set_processed_file(item.media_ref, result.path.name)
            processed.append(item.media_ref)
    finally:
        if own_client:
            client.close()
    return {"processed": len(processed), "failed": failed, "remaining": len(todo) - len(processed)}
