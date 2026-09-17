"""Where captured_at came from, kept distinguishable from the timestamp itself.

Videos carry no EXIF, so their capture time has to come from the MP4
container's own creation_time, and failing that from Drive's upload time.
Those are not the same kind of fact: an upload time says when the file
arrived, not when it was shot. Stored in one column with no marker, the two
would be indistinguishable and chronological/story ordering would silently
sort an item as if it had been filmed on the day it was uploaded.
"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.instagram_content.captured_at_resolution import (
    CapturedAtSource,
    is_plausible_capture_time,
    parse_capture_time_from_filename,
    resolve_captured_at,
)
from app.instagram_content.media_pool_models import (
    MediaPoolIngestRequest,
    MediaPoolItemCreate,
)
from app.instagram_content.media_pool_service import MediaPoolService
from app.instagram_content.models import MediaType

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
SHOT = datetime(2026, 9, 14, 8, 30, tzinfo=timezone.utc)
UPLOADED = datetime(2026, 9, 15, 19, 5, tzinfo=timezone.utc)

#: What an MP4 with no creation_time written decodes to: the format counts
#: from 1904-01-01 and a missing field is a zero.
MP4_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)


# -- plausibility -----------------------------------------------------------


def test_a_real_timestamp_is_plausible():
    assert is_plausible_capture_time(SHOT, now=NOW) is True


def test_the_zeroed_mp4_field_is_not_a_timestamp():
    """The decisive case: without this check a zeroed mvhd field would win
    over a perfectly good upload time, because it is checked first."""
    assert is_plausible_capture_time(MP4_EPOCH, now=NOW) is False


def test_a_zeroed_unix_timestamp_is_not_a_timestamp():
    assert is_plausible_capture_time(datetime(1970, 1, 1, tzinfo=timezone.utc), now=NOW) is False


def test_a_clock_running_slightly_ahead_is_tolerated():
    assert is_plausible_capture_time(NOW + timedelta(hours=6), now=NOW) is True


def test_a_timestamp_far_in_the_future_is_rejected():
    assert is_plausible_capture_time(NOW + timedelta(days=30), now=NOW) is False


def test_none_is_not_plausible():
    assert is_plausible_capture_time(None, now=NOW) is False


# -- a date written into the file name --------------------------------------


@pytest.mark.parametrize(
    "file_name,expected",
    [
        ("2026-03-05_1430_valencia.mp4", datetime(2026, 3, 5, 14, 30, tzinfo=timezone.utc)),
        ("2026-03-05.mp4", datetime(2026, 3, 5, 0, 0, tzinfo=timezone.utc)),
        ("20260305_143022.mov", datetime(2026, 3, 5, 14, 30, 22, tzinfo=timezone.utc)),
        ("2026_03_05 gym.mp4", datetime(2026, 3, 5, 0, 0, tzinfo=timezone.utc)),
        ("IMG_20260305_1430.jpg", datetime(2026, 3, 5, 14, 30, tzinfo=timezone.utc)),
        ("VID-2026-03-05T14-30.mp4", datetime(2026, 3, 5, 14, 30, tzinfo=timezone.utc)),
    ],
)
def test_a_date_at_the_start_of_the_name_is_read(file_name, expected):
    assert parse_capture_time_from_filename(file_name) == expected


@pytest.mark.parametrize(
    "file_name",
    [
        "IMG_2922.mp4",                 # a camera counter, not a date
        "clip_4k_2020.mp4",             # a number further along the name
        "valencia_2026-03-05.mp4",      # not at the start: a coincidence, not a statement
        "2026-13-45_broken.mp4",        # shaped like a date, isn't one
        "202603051.mp4",                # more digits than a date has
        "",
        None,
    ],
)
def test_anything_that_is_not_a_leading_date_is_ignored(file_name):
    assert parse_capture_time_from_filename(file_name) is None


def test_the_file_name_outranks_every_automatic_source():
    """The Lightroom case, exactly: 30 clips shot on different days were all
    re-exported in one afternoon, so every container claimed that afternoon.
    A human-written name is the only source that survives that, so it wins."""
    lightroom_export = datetime(2026, 3, 3, 12, 16, 32, tzinfo=timezone.utc)
    value, source = resolve_captured_at(
        file_name="2026-02-14_1830_gym.mp4",
        exif=SHOT,
        video_creation_time=lightroom_export,
        upload_time=UPLOADED,
        now=NOW,
    )
    assert (value, source) == (datetime(2026, 2, 14, 18, 30, tzinfo=timezone.utc), CapturedAtSource.filename)


def test_an_undated_name_falls_through_instead_of_blocking_the_other_sources():
    value, source = resolve_captured_at(file_name="IMG_2922.mp4", exif=SHOT, now=NOW)
    assert (value, source) == (SHOT, CapturedAtSource.exif)


def test_a_photo_never_has_its_name_read(monkeypatch):
    """Images are excluded at the call site in analyze_and_ingest, not here:
    a photo's EXIF is a fact, a file name is typed by hand, and a typo must
    not outrank the shutter. resolve_captured_at stays general -- the caller
    decides whether a name is even offered."""
    import base64
    import json as json_module

    import httpx

    from app.instagram_content.analyze_and_ingest import analyze_and_ingest
    from app.instagram_content.media_pool_models import MediaAnalyzeAndIngestItem
    from app.instagram_content.vision_analysis import AnthropicVisionAnalyzer, VisionAnalysisConfig

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": json_module.dumps(
            {"theme": "desert-gold", "tags": ["sand"], "aesthetic_score": 0.7, "reasoning": "ok"}
        )}]})

    analyzer = AnthropicVisionAnalyzer(
        config=VisionAnalysisConfig(api_key="test-key"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    pool = MediaPoolService()
    pool.reset()

    analyze_and_ingest([
        MediaAnalyzeAndIngestItem(
            media_ref="photo-with-dated-name",
            media_type=MediaType.image,
            file_name="2020-01-01_wrong.jpg",
            image_base64=base64.b64encode(b"not-a-real-jpeg").decode("ascii"),
            image_media_type="image/jpeg",
        )
    ], analyzer, pool)

    stored = pool.list_all()[0]
    assert stored.captured_at_source != CapturedAtSource.filename
    assert stored.captured_at is None, "no EXIF in these bytes, and the name must not stand in for it"


def test_a_name_dated_in_the_future_is_refused_like_any_other_source():
    """A typo (2036 for 2026) must not sort an item years ahead of everything."""
    value, source = resolve_captured_at(file_name="2036-03-05_gym.mp4", exif=SHOT, now=NOW)
    assert (value, source) == (SHOT, CapturedAtSource.exif)


# -- source selection -------------------------------------------------------


def test_exif_wins_over_everything_automatic():
    value, source = resolve_captured_at(
        exif=SHOT, video_creation_time=datetime(2026, 9, 15, tzinfo=timezone.utc),
        upload_time=UPLOADED, now=NOW,
    )
    assert (value, source) == (SHOT, CapturedAtSource.exif)


def test_video_metadata_wins_over_the_upload_time():
    value, source = resolve_captured_at(video_creation_time=SHOT, upload_time=UPLOADED, now=NOW)
    assert (value, source) == (SHOT, CapturedAtSource.video_metadata)


def test_the_upload_time_is_used_only_when_nothing_better_exists():
    value, source = resolve_captured_at(upload_time=UPLOADED, now=NOW)
    assert (value, source) == (UPLOADED, CapturedAtSource.upload_time)


def test_a_zeroed_video_creation_time_falls_through_to_the_upload_time():
    """A video exported by a tool that wrote no creation_time. Without the
    plausibility gate this would store 1904 and call it a capture time."""
    value, source = resolve_captured_at(video_creation_time=MP4_EPOCH, upload_time=UPLOADED, now=NOW)
    assert (value, source) == (UPLOADED, CapturedAtSource.upload_time)


def test_nothing_plausible_yields_nothing_rather_than_an_invented_time():
    assert resolve_captured_at(video_creation_time=MP4_EPOCH, now=NOW) == (None, None)
    assert resolve_captured_at(now=NOW) == (None, None)


def test_a_naive_timestamp_comes_back_as_utc():
    value, source = resolve_captured_at(exif=datetime(2026, 9, 14, 8, 30), now=NOW)
    assert value == SHOT
    assert value.tzinfo is not None
    assert source is CapturedAtSource.exif


# -- the model keeps the two together --------------------------------------


def test_a_timestamp_without_its_source_is_refused():
    with pytest.raises(ValidationError, match="captured_at_source"):
        MediaPoolItemCreate(
            media_ref="drive-1", media_type=MediaType.image, theme="gym", tags=["gym"],
            aesthetic_score=0.5, captured_at=SHOT,
        )


def test_a_source_without_a_timestamp_is_refused():
    with pytest.raises(ValidationError, match="captured_at_source"):
        MediaPoolItemCreate(
            media_ref="drive-1", media_type=MediaType.image, theme="gym", tags=["gym"],
            aesthetic_score=0.5, captured_at_source=CapturedAtSource.exif,
        )


def test_neither_set_is_fine():
    item = MediaPoolItemCreate(
        media_ref="drive-1", media_type=MediaType.image, theme="gym", tags=["gym"], aesthetic_score=0.5
    )
    assert item.captured_at is None and item.captured_at_source is None


def test_an_upload_time_stays_marked_as_one_through_storage():
    """The point of the whole field: after a round trip through the pool it
    is still visible that this timestamp is not a capture time."""
    service = MediaPoolService()
    service.reset()
    service.ingest(MediaPoolIngestRequest(items=[MediaPoolItemCreate(
        media_ref="drive-video-1", media_type=MediaType.video, theme="2026-09-15", tags=[],
        aesthetic_score=0.6, duration_seconds=9.3,
        captured_at=UPLOADED, captured_at_source=CapturedAtSource.upload_time,
    )]))

    stored = service.list_all()[0]
    assert stored.captured_at == UPLOADED
    assert stored.captured_at_source is CapturedAtSource.upload_time
    assert '"captured_at_source":"upload_time"' in stored.model_dump_json().replace(" ", "")


def test_a_re_analysis_carries_the_new_source_with_the_new_timestamp():
    """captured_at_source travels with captured_at through the update path --
    otherwise an item re-analyzed from real video metadata would keep the
    stale 'upload_time' marker and look worse than it is."""
    service = MediaPoolService()
    service.reset()
    service.ingest(MediaPoolIngestRequest(items=[MediaPoolItemCreate(
        media_ref="drive-video-1", media_type=MediaType.video, theme="video", tags=[],
        aesthetic_score=0.6, duration_seconds=9.3,
        captured_at=UPLOADED, captured_at_source=CapturedAtSource.upload_time,
    )]))

    service.ingest(MediaPoolIngestRequest(items=[MediaPoolItemCreate(
        media_ref="drive-video-1", media_type=MediaType.video, theme="gym-mirror-selfie",
        tags=["gym"], aesthetic_score=0.8, duration_seconds=9.3,
        captured_at=SHOT, captured_at_source=CapturedAtSource.video_metadata,
    )]))

    stored = service.list_all()[0]
    assert stored.captured_at == SHOT
    assert stored.captured_at_source is CapturedAtSource.video_metadata
    assert stored.analysis_complete is True


# -- migrating the rows written before the field existed ---------------------


def _write_legacy_row(payload: dict) -> None:
    """A row exactly as it sits in the live db: captured_at, no source."""
    import json

    from app.db import SessionLocal
    from app.db_models import InstagramMediaPoolItemRow

    with SessionLocal() as session:
        session.add(InstagramMediaPoolItemRow(
            id=payload["id"], media_ref=payload["media_ref"], data=json.dumps(payload),
        ))
        session.commit()


def _legacy_image(media_ref: str, item_id: str) -> dict:
    return {
        "media_ref": media_ref, "media_type": "image", "theme": "gym-mirror-selfie",
        "tags": ["gym"], "aesthetic_score": 0.7, "captured_at": "2026-09-14T08:30:00Z",
        "analyzed_at": "2026-09-14T11:01:09Z", "id": item_id, "used": False,
    }


def test_a_legacy_row_cannot_even_be_loaded_before_the_backfill():
    """Why this migration is not optional: the model now requires the pair,
    so every pre-existing image row fails validation until it is filled."""
    from app.instagram_content.media_pool_models import MediaPoolItem

    with pytest.raises(ValidationError, match="captured_at_source"):
        MediaPoolItem.model_validate(_legacy_image("drive-legacy", "11111111-1111-4111-8111-111111111111"))


def test_the_backfill_fills_legacy_image_rows_with_exif_and_makes_them_loadable():
    service = MediaPoolService()
    service.reset()
    _write_legacy_row(_legacy_image("drive-legacy-1", "11111111-1111-4111-8111-111111111111"))

    report = service.backfill_captured_at_source()

    assert report["filled_exif"] == 1
    stored = service.list_all()[0]
    assert stored.captured_at_source is CapturedAtSource.exif
    assert stored.captured_at == datetime(2026, 9, 14, 8, 30, tzinfo=timezone.utc)


def test_the_backfill_is_idempotent():
    service = MediaPoolService()
    service.reset()
    _write_legacy_row(_legacy_image("drive-legacy-1", "11111111-1111-4111-8111-111111111111"))

    first = service.backfill_captured_at_source()
    second = service.backfill_captured_at_source()

    assert first["filled_exif"] == 1
    assert second["filled_exif"] == 0
    assert second["already_had_a_source"] == 1


def test_the_backfill_leaves_rows_without_a_timestamp_alone():
    """The 30 placeholder videos: no captured_at, so nothing to attribute."""
    service = MediaPoolService()
    service.reset()
    service.ingest(MediaPoolIngestRequest(items=[MediaPoolItemCreate(
        media_ref="drive-video-1", media_type=MediaType.video, theme="video", tags=[],
        aesthetic_score=0.6, duration_seconds=9.3,
    )]))

    report = service.backfill_captured_at_source()

    assert report == {"filled_exif": 0, "already_had_a_source": 0, "non_image_left_untouched": 0}
    assert service.list_all()[0].captured_at_source is None


def test_a_video_row_with_an_unexplained_timestamp_is_reported_not_guessed_at():
    """EXIF cannot come from a video, so 'exif' would be an invention here.
    Such a row is surfaced in the report instead of being filled silently."""
    service = MediaPoolService()
    service.reset()
    legacy_video = _legacy_image("drive-video-legacy", "22222222-2222-4222-8222-222222222222")
    legacy_video.update(media_type="video", duration_seconds=9.3, theme="video", tags=[])
    _write_legacy_row(legacy_video)

    report = service.backfill_captured_at_source()

    assert report["filled_exif"] == 0
    assert report["non_image_left_untouched"] == 1
