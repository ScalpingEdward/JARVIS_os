"""Grading the photos that were analyzed before photos were graded at all.

Their bytes are gone from the ingest directory (the sweeper empties it
within a day), so each one is fetched back from Drive through n8n, graded
exactly like a new photo at ingest, and recorded. The next ingest run then
uploads the graded file to "AURON fertig" like any other.

One call handles a bounded batch on purpose: 265 photos at a few seconds
each is several minutes, longer than any single request should hold a
connection open, and a batch that fails halfway has still saved its work.
"""

from __future__ import annotations

import httpx

from .analyze_and_ingest import grade_photo_bytes
from .drive_fetch import DriveFetchError, fetch_drive_file
from .media_pool_models import MediaPoolItem
from .media_pool_service import media_pool_service
from .models import MediaType


def ungraded_photos() -> list[MediaPoolItem]:
    return [
        item for item in media_pool_service.list_all()
        if item.media_type == MediaType.image and not item.processed_file
    ]


def grade_existing_photos(limit: int = 20, client: httpx.Client | None = None) -> dict:
    todo = ungraded_photos()
    batch = todo[:limit]
    graded: list[str] = []
    failed: dict[str, str] = {}
    own_client = client is None
    client = client or httpx.Client()
    try:
        for item in batch:
            try:
                data = fetch_drive_file(client, item.media_ref)
            except DriveFetchError as exc:
                failed[item.media_ref] = str(exc)
                continue
            name = grade_photo_bytes(data, item.media_ref)
            if name is None:
                failed[item.media_ref] = "grading failed (see api log)"
                continue
            media_pool_service.set_processed_file(item.media_ref, name)
            graded.append(item.media_ref)
    finally:
        if own_client:
            client.close()
    return {
        "graded": len(graded),
        "failed": failed,
        "remaining": len(todo) - len(graded),
    }


def regrade_developed_photos(
    limit: int = 20, offset: int = 0, client: httpx.Client | None = None,
    which: str = "developed",
) -> dict:
    """Re-grade the photos that were graded twice.

    Until the LUT was skipped for files that had already been through
    Lightroom, every photo got the same chain -- so an export carrying
    Brano's look in its pixels received it a second time, and looked garish
    next to an untouched camera file that had received it once.

    Only the exports are rewritten. A camera original run through the same
    unchanged chain would come out byte-for-byte as it already is, so it is
    fetched (the EXIF is the only way to tell the two apart), checked, and
    left alone. Bounded like the first pass, and walked by `offset` so a
    batch that decides to skip everything still makes progress.
    """
    import tempfile
    from pathlib import Path

    from .media_processing import developed_by

    photos = sorted(
        (i for i in media_pool_service.list_all() if i.media_type == MediaType.image),
        key=lambda i: i.media_ref,
    )
    batch = photos[offset:offset + limit]
    regraded: list[str] = []
    camera_originals = 0
    failed: dict[str, str] = {}
    own_client = client is None
    client = client or httpx.Client()
    try:
        for item in batch:
            try:
                data = fetch_drive_file(client, item.media_ref)
            except DriveFetchError as exc:
                failed[item.media_ref] = str(exc)
                continue
            handle = tempfile.NamedTemporaryFile(suffix=".img", delete=False)
            try:
                handle.write(data)
                handle.close()
                editor = developed_by(Path(handle.name))
            finally:
                Path(handle.name).unlink(missing_ok=True)
            wanted = (editor is None) if which == "camera" else (editor is not None)
            if not wanted:
                camera_originals += 1
                continue
            name = grade_photo_bytes(data, item.media_ref)
            if name is None:
                failed[item.media_ref] = "grading failed (see api log)"
                continue
            media_pool_service.set_processed_file(item.media_ref, name)
            regraded.append(item.media_ref)
    finally:
        if own_client:
            client.close()
    return {
        "regraded": len(regraded),
        "camera_originals_left_alone": camera_originals,
        "failed": failed,
        "next_offset": offset + len(batch),
        "photos_total": len(photos),
    }
