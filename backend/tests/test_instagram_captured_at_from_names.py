"""Recovering a shoot date from a renamed file, without paying twice.

Renaming a file in Drive keeps its id, so the media_ref -- and the vision
analysis already paid for -- survives. What does not happen by itself is
anyone reading the new name: the ingest pre-filter skips any media_ref that
is already fully analyzed, so those files are never downloaded or looked at
again. Without this path, renaming the 31 Lightroom-exported videos would
have changed nothing at all, and the alternative (delete, re-upload,
re-analyze) would have cost 31 fresh vision calls.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.instagram_content.captured_at_resolution import CapturedAtSource
from app.instagram_content.media_pool_models import (
    CapturedAtFromNameItem,
    CapturedAtFromNameRequest,
    MediaPoolIngestRequest,
    MediaPoolItemCreate,
)
from app.instagram_content.media_pool_service import MediaPoolService


@pytest.fixture(autouse=True)
def _clean():
    MediaPoolService().reset()
    yield


def _pool_with(*creates) -> MediaPoolService:
    pool = MediaPoolService()
    pool.ingest(MediaPoolIngestRequest(items=list(creates)))
    return pool


def _analyzed_video(ref: str, **overrides) -> MediaPoolItemCreate:
    """A video exactly as it sits in the pool after a real analysis: theme
    and tags are real, captured_at is missing because Lightroom's export
    destroyed it."""
    payload = dict(
        media_ref=ref, media_type="video", theme="riverside-park-walk",
        tags=["park", "river"], aesthetic_score=0.55, duration_seconds=16.6,
    )
    payload.update(overrides)
    return MediaPoolItemCreate(**payload)


def _request(*pairs) -> CapturedAtFromNameRequest:
    return CapturedAtFromNameRequest(
        items=[CapturedAtFromNameItem(media_ref=r, file_name=n) for r, n in pairs]
    )


def test_a_renamed_video_gets_its_shoot_day_without_being_re_analyzed():
    pool = _pool_with(_analyzed_video("drive-id-1"))

    result = pool.captured_at_from_names(_request(("drive-id-1", "2026-03-05_1430.mp4")))

    assert result.filled == 1
    item = pool.list_all()[0]
    assert item.captured_at == datetime(2026, 3, 5, 14, 30, tzinfo=timezone.utc)
    assert item.captured_at_source == CapturedAtSource.filename
    assert item.theme == "riverside-park-walk", "the paid-for analysis must survive untouched"
    assert item.tags == ["park", "river"]
    assert item.aesthetic_score == 0.55


def test_an_existing_date_is_never_overwritten():
    """A date already there came from EXIF or the container. A name typed
    later is not grounds to replace a measured value."""
    exif_date = datetime(2025, 10, 26, 9, 0, tzinfo=timezone.utc)
    pool = _pool_with(MediaPoolItemCreate(
        media_ref="photo-1", media_type="image", theme="desert-gold", tags=["sand"],
        aesthetic_score=0.8, captured_at=exif_date, captured_at_source=CapturedAtSource.exif,
    ))

    result = pool.captured_at_from_names(_request(("photo-1", "2020-01-01_wrong.jpg")))

    assert result.already_had_one == 1
    assert result.filled == 0
    item = pool.list_all()[0]
    assert item.captured_at == exif_date
    assert item.captured_at_source == CapturedAtSource.exif


def test_a_name_without_a_date_leaves_the_item_alone():
    """No date is an honest state. Inventing one would be the failure."""
    pool = _pool_with(_analyzed_video("drive-id-2"))

    result = pool.captured_at_from_names(_request(("drive-id-2", "IMG_2922.mp4")))

    assert (result.filled, result.no_date_in_name) == (0, 1)
    assert pool.list_all()[0].captured_at is None


def test_an_implausible_date_in_a_name_is_refused():
    """A typo (2036 for 2026) would sort an item years ahead of everything
    else and never be noticed."""
    pool = _pool_with(_analyzed_video("drive-id-3"))

    result = pool.captured_at_from_names(_request(("drive-id-3", "2036-03-05_1430.mp4")))

    assert result.no_date_in_name == 1
    assert pool.list_all()[0].captured_at is None


def test_an_unknown_media_ref_is_counted_not_an_error():
    """The caller sends every file in the folder; most are already dated or
    not in the pool. That is normal traffic, not a failure."""
    pool = _pool_with(_analyzed_video("drive-id-4"))

    result = pool.captured_at_from_names(_request(
        ("drive-id-4", "2026-03-05.mp4"),
        ("never-seen-this", "2026-03-06.mp4"),
    ))

    assert (result.filled, result.unknown_media_ref) == (1, 1)


def test_the_report_distinguishes_every_outcome():
    """A backfill that silently did nothing looks identical to one that
    worked, unless it says which happened -- that exact silence already
    cost this project a full run of paid analyses once."""
    pool = _pool_with(
        _analyzed_video("v-dated"),
        _analyzed_video("v-undated"),
        MediaPoolItemCreate(
            media_ref="p-has-exif", media_type="image", theme="desert-gold", tags=["sand"],
            aesthetic_score=0.8, captured_at=datetime(2025, 5, 1, tzinfo=timezone.utc),
            captured_at_source=CapturedAtSource.exif,
        ),
    )

    result = pool.captured_at_from_names(_request(
        ("v-dated", "2026-03-05_0900.mp4"),
        ("v-undated", "clip_final_v2.mp4"),
        ("p-has-exif", "2026-03-05_0900.jpg"),
        ("gone", "2026-03-05_0900.mp4"),
    ))

    assert result.filled == 1
    assert result.already_had_one == 1
    assert result.no_date_in_name == 1
    assert result.unknown_media_ref == 1
    assert result.filled_refs == ["v-dated"]


def test_running_it_twice_changes_nothing_the_second_time():
    pool = _pool_with(_analyzed_video("drive-id-5"))
    request = _request(("drive-id-5", "2026-03-05_1430.mp4"))

    first = pool.captured_at_from_names(request)
    second = pool.captured_at_from_names(request)

    assert first.filled == 1
    assert (second.filled, second.already_had_one) == (0, 1)


def test_the_recovered_date_actually_drives_the_posting_order():
    """The point of the whole exercise: a recovered day has to place the
    video in the queue, not just sit in a column."""
    from datetime import date

    from app.instagram_content.curation import curate

    pool = _pool_with(_analyzed_video("v-older"), _analyzed_video("v-newer"))
    pool.captured_at_from_names(_request(
        ("v-newer", "2026-03-10_1200.mp4"),
        ("v-older", "2026-02-14_1800.mp4"),
    ))

    groups = curate(pool.list_available())

    assert [g.day for g in groups] == [date(2026, 2, 14), date(2026, 3, 10)]
