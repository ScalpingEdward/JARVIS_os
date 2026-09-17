from __future__ import annotations

import base64
import json
import os
from datetime import date
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.instagram_content.analyze_and_ingest import analyze_and_ingest
from app.instagram_content.curation import CAROUSEL_IDEAL_MAX_SIZE, CAROUSEL_MIN_SIZE, ELITE_SOLO_THRESHOLD, curate
from app.instagram_content.media_pool_models import (
    FinalizeDraftRequest,
    MediaAnalyzeAndIngestItem,
    MediaPoolIngestRequest,
    MediaPoolItemCreate,
)
from app.instagram_content.media_pool_service import MediaPoolError, MediaPoolService
from app.instagram_content.models import ContentStatus, PostFormat
from app.instagram_content.publisher import N8nInstagramPublisher
from app.instagram_content.service import InstagramContentError, InstagramContentService
from app.instagram_content.vision_analysis import AnthropicVisionAnalyzer, VisionAnalysisConfig


@pytest.fixture(autouse=True)
def _reset_shared_state():
    """Storage is now real and shared rather than fresh-per-instance
    in-memory -- see MediaPoolService's own docstring. Tests in this file
    reuse fixed media_refs across each other, so each test needs a clean
    slate."""
    MediaPoolService().reset()
    InstagramContentService().reset()
    yield


def _image_create(ref, theme="desert-gold", score=0.6):
    return MediaPoolItemCreate(media_ref=ref, media_type="image", theme=theme, aesthetic_score=score)


def _video_create(ref, theme="desert-gold", score=0.6, duration=25.0):
    return MediaPoolItemCreate(media_ref=ref, media_type="video", theme=theme, aesthetic_score=score, duration_seconds=duration)


# -- curate() unit tests: pure grouping logic --------------------------------


def test_curate_groups_same_theme_images_into_one_carousel():
    from app.instagram_content.media_pool_models import MediaPoolItem

    items = [MediaPoolItem(**_image_create(f"img-{i}", score=0.7).model_dump()) for i in range(4)]
    groups = curate(items)
    assert len(groups) == 1
    assert len(groups[0].media_items) == 4


def test_curate_splits_a_large_theme_into_multiple_right_sized_carousels():
    from app.instagram_content.media_pool_models import MediaPoolItem

    n = CAROUSEL_IDEAL_MAX_SIZE + CAROUSEL_MIN_SIZE  # guarantees a full batch + a valid remainder
    items = [MediaPoolItem(**_image_create(f"img-{i}", score=0.6).model_dump()) for i in range(n)]
    groups = curate(items)
    sizes = sorted(len(g.media_items) for g in groups)
    assert sizes[0] >= CAROUSEL_MIN_SIZE
    assert sizes[-1] <= CAROUSEL_IDEAL_MAX_SIZE
    assert sum(sizes) == n


def test_curate_does_not_propose_a_carousel_below_the_minimum_size():
    from app.instagram_content.media_pool_models import MediaPoolItem

    items = [MediaPoolItem(**_image_create(f"img-{i}", score=0.5).model_dump()) for i in range(2)]
    groups = curate(items)
    assert groups == []  # 2 items, below CAROUSEL_MIN_SIZE=3, deliberately left unposted


def test_curate_gives_an_elite_image_its_own_hero_post():
    from app.instagram_content.media_pool_models import MediaPoolItem

    strong = MediaPoolItem(**_image_create("hero", score=ELITE_SOLO_THRESHOLD + 0.05).model_dump())
    others = [MediaPoolItem(**_image_create(f"img-{i}", score=0.5).model_dump()) for i in range(3)]
    groups = curate([strong, *others])

    hero_groups = [g for g in groups if len(g.media_items) == 1 and g.media_items[0].media_ref == "hero"]
    assert len(hero_groups) == 1


def test_curate_elite_solo_threshold_is_a_hard_boundary():
    """Locks in the >= comparison in curation.py: a score exactly at the
    threshold is elite (hero), a score just below it is not (carousel)."""
    from app.instagram_content.media_pool_models import MediaPoolItem

    just_below = MediaPoolItem(**_image_create("just-below", score=ELITE_SOLO_THRESHOLD - 0.01).model_dump())
    at_threshold = MediaPoolItem(**_image_create("at-threshold", score=ELITE_SOLO_THRESHOLD).model_dump())
    just_above = MediaPoolItem(**_image_create("just-above", score=ELITE_SOLO_THRESHOLD + 0.01).model_dump())
    filler = [MediaPoolItem(**_image_create(f"filler-{i}", score=0.5).model_dump()) for i in range(2)]

    groups = curate([just_below, at_threshold, just_above, *filler])

    hero_refs = {g.media_items[0].media_ref for g in groups if len(g.media_items) == 1}
    assert hero_refs == {"at-threshold", "just-above"}

    carousel_groups = [g for g in groups if len(g.media_items) > 1]
    assert len(carousel_groups) == 1
    carousel_refs = {m.media_ref for m in carousel_groups[0].media_items}
    assert carousel_refs == {"just-below", "filler-0", "filler-1"}


def test_curate_always_puts_a_video_alone():
    from app.instagram_content.media_pool_models import MediaPoolItem

    video = MediaPoolItem(**_video_create("clip", score=0.5).model_dump())
    images = [MediaPoolItem(**_image_create(f"img-{i}", score=0.5).model_dump()) for i in range(3)]
    groups = curate([video, *images])

    video_groups = [g for g in groups if any(m.media_type == "video" for m in g.media_items)]
    assert len(video_groups) == 1
    assert len(video_groups[0].media_items) == 1


def test_curate_orders_groups_by_shoot_day_oldest_first_never_interleaving_days():
    """Brano's actual requirement: if one day produces several posts (a
    carousel, a reel, a single), they must all go out together before the
    next day's content starts -- never interleaved by score across days."""
    from datetime import datetime, timezone

    from app.instagram_content.captured_at_resolution import CapturedAtSource
    from app.instagram_content.media_pool_models import MediaPoolItem

    def _dated(ref, day, score, media_type="image"):
        payload = dict(
            media_ref=ref, media_type=media_type, theme="desert-gold", aesthetic_score=score,
            captured_at=datetime(*day, tzinfo=timezone.utc), captured_at_source=CapturedAtSource.exif,
        )
        if media_type == "video":
            payload["duration_seconds"] = 20.0
        return MediaPoolItem(**payload)

    below_elite = ELITE_SOLO_THRESHOLD - 0.1
    above_elite = ELITE_SOLO_THRESHOLD + 0.1

    # Older day: a video (high score) and enough low-score images for exactly
    # one carousel.
    old_day = [
        _dated("old-video", (2026, 9, 10), above_elite, media_type="video"),
        *[_dated(f"old-img-{i}", (2026, 9, 10), below_elite) for i in range(CAROUSEL_MIN_SIZE)],
    ]
    # Newer day: a single elite image with a higher score than anything above.
    new_day = [_dated("new-hero", (2026, 9, 12), above_elite + 0.001)]
    # No captured_at at all -- must sort after every dated day regardless of score.
    undated = [MediaPoolItem(**_image_create("undated-hero", score=above_elite + 0.001).model_dump())]

    groups = curate([*new_day, *undated, *old_day])

    days = [g.day for g in groups]
    assert days == [date(2026, 9, 10), date(2026, 9, 10), date(2026, 9, 12), None]


def test_curate_ignores_items_that_are_not_available():
    from app.instagram_content.media_pool_models import MediaPoolItem
    from uuid import uuid4

    used_item = MediaPoolItem(**_image_create("a").model_dump())
    used_item.used = True
    reserved_item = MediaPoolItem(**_image_create("b").model_dump())
    reserved_item.reserved_in_draft_id = uuid4()
    available = [MediaPoolItem(**_image_create(f"c{i}").model_dump()) for i in range(3)]

    groups = curate([used_item, reserved_item, *available])
    all_refs = {m.media_ref for g in groups for m in g.media_items}
    assert "a" not in all_refs
    assert "b" not in all_refs


# -- media pool service: ingest, dedup, reservation --------------------------


def test_ingest_skips_duplicate_media_refs():
    pool = MediaPoolService()
    response = pool.ingest(MediaPoolIngestRequest(items=[_image_create("dup"), _image_create("dup")]))
    assert response.ingested == 1
    assert response.skipped_duplicates == 1


def test_run_curation_reserves_items_so_a_second_run_does_not_reuse_them():
    pool = MediaPoolService()
    pool.ingest(MediaPoolIngestRequest(items=[_image_create(f"img-{i}") for i in range(4)]))

    first_drafts = pool.run_curation()
    assert sum(len(d.media_item_ids) for d in first_drafts) == 4
    assert pool.list_available() == []  # all 4 are now reserved

    second_drafts = pool.run_curation()
    assert second_drafts == []  # nothing left to propose


def test_pending_drafts_are_ordered_by_shoot_day_not_creation_time():
    """The actual queue Brano works from (GET /curate/drafts, pending_only
    default True): a draft from an older shoot day must come first, even if
    a newer day's draft happened to be curated (created) earlier in real
    time -- otherwise the two days' content would interleave in whatever
    order the daily ingest run curated them."""
    from datetime import datetime, timezone

    from app.instagram_content.captured_at_resolution import CapturedAtSource

    pool = MediaPoolService()
    newer = MediaPoolItemCreate(
        media_ref="newer-hero", media_type="image", theme="desert-gold",
        aesthetic_score=ELITE_SOLO_THRESHOLD + 0.1,
        captured_at=datetime(2026, 9, 12, tzinfo=timezone.utc), captured_at_source=CapturedAtSource.exif,
    )
    older = MediaPoolItemCreate(
        media_ref="older-hero", media_type="image", theme="desert-gold",
        aesthetic_score=ELITE_SOLO_THRESHOLD + 0.1,
        captured_at=datetime(2026, 9, 10, tzinfo=timezone.utc), captured_at_source=CapturedAtSource.exif,
    )
    pool.ingest(MediaPoolIngestRequest(items=[newer]))
    pool.run_curation()  # the newer day's draft is created first, in real time
    pool.ingest(MediaPoolIngestRequest(items=[older]))
    pool.run_curation()  # the older day's draft is created second

    pending = pool.list_drafts(pending_only=True)
    assert [d.theme for d in pending] == ["2026-09-10", "2026-09-12"]


def test_discard_draft_returns_items_to_the_available_pool():
    pool = MediaPoolService()
    pool.ingest(MediaPoolIngestRequest(items=[_image_create(f"img-{i}") for i in range(4)]))
    drafts = pool.run_curation()
    draft_id = drafts[0].id

    pool.discard_draft(draft_id)
    assert len(pool.list_available()) == 4


def test_cannot_discard_a_finalized_draft():
    pool = MediaPoolService()
    pool.ingest(MediaPoolIngestRequest(items=[_image_create(f"img-{i}") for i in range(4)]))
    draft = pool.run_curation()[0]
    pool.mark_finalized(draft.id, candidate_id=draft.id)  # candidate_id value doesn't matter for this test

    with pytest.raises(MediaPoolError, match="already"):
        pool.discard_draft(draft.id)


# -- finalize_draft: the full automated flow ---------------------------------


def _service_with_mock_publisher(handler):
    transport = httpx.MockTransport(handler)
    publisher = N8nInstagramPublisher(client=httpx.Client(transport=transport))
    return InstagramContentService(publisher=publisher)


def test_finalize_draft_creates_a_real_candidate_and_marks_photos_used(monkeypatch):
    from app.instagram_content import media_pool_service as pool_module

    pool_module.media_pool_service.reset()
    pool_module.media_pool_service.ingest(MediaPoolIngestRequest(items=[_image_create(f"img-{i}") for i in range(4)]))
    draft = pool_module.media_pool_service.run_curation()[0]

    service = _service_with_mock_publisher(lambda r: httpx.Response(200, json={"media_id": "x"}))
    candidate = service.finalize_draft(
        draft.id, FinalizeDraftRequest(caption_draft="Quiet mornings build the account. #tradingmindset #discipline #patience")
    )

    assert candidate.status == ContentStatus.proposed
    assert candidate.post_format == PostFormat.carousel
    refreshed_draft = pool_module.media_pool_service.get_draft(draft.id)
    assert refreshed_draft.finalized is True
    for item_id in refreshed_draft.media_item_ids:
        assert pool_module.media_pool_service.get(item_id).used is True


def test_finalize_draft_with_bad_caption_leaves_photos_available_for_retry():
    from app.instagram_content import media_pool_service as pool_module

    pool_module.media_pool_service.reset()
    pool_module.media_pool_service.ingest(MediaPoolIngestRequest(items=[_image_create(f"img-{i}") for i in range(4)]))
    draft = pool_module.media_pool_service.run_curation()[0]

    service = _service_with_mock_publisher(lambda r: httpx.Response(200, json={"media_id": "x"}))
    candidate = service.finalize_draft(draft.id, FinalizeDraftRequest(caption_draft="Follow4follow please!!"))

    assert candidate.status == ContentStatus.moderation_rejected
    refreshed_draft = pool_module.media_pool_service.get_draft(draft.id)
    assert refreshed_draft.finalized is False  # left pending, not consumed
    for item_id in refreshed_draft.media_item_ids:
        assert pool_module.media_pool_service.get(item_id).used is False


def test_finalize_unknown_draft_fails_closed():
    from uuid import uuid4

    service = _service_with_mock_publisher(lambda r: httpx.Response(200, json={"media_id": "x"}))
    with pytest.raises(InstagramContentError, match="not found"):
        service.finalize_draft(uuid4(), FinalizeDraftRequest(caption_draft="Anything"))


def test_pool_items_and_drafts_survive_a_fresh_service_instance():
    """The actual fix, and exactly what the external test pass named:
    'Instagram-Entwuerfe, Medienreservierungen' -- a genuinely fresh
    service instance sees exactly what a previous one ingested and
    curated, including which items are reserved in which draft."""
    first = MediaPoolService()
    first.ingest(MediaPoolIngestRequest(items=[_image_create(f"restart-{i}") for i in range(4)]))
    drafts = first.run_curation()
    assert len(drafts) >= 1
    draft_id = drafts[0].id

    second = MediaPoolService()  # nothing shared but the real database
    restored_draft = second.get_draft(draft_id)
    assert restored_draft.id == draft_id
    # the reservation itself must have survived -- these items must not
    # be available for a second curation run
    available_refs = {item.media_ref for item in second.list_available()}
    reserved_refs = {second.get(item_id).media_ref for item_id in restored_draft.media_item_ids}
    assert available_refs.isdisjoint(reserved_refs)


# -- analyze_and_ingest: oversized-image downscale ---------------------------


def _oversized_jpeg_with_exif_base64(captured_at_str="2024:01:15 10:30:00"):
    """A JPEG whose longest edge is well above the 2000px downscale
    threshold, with real EXIF DateTimeOriginal so the test can check that
    reading it still works after -- and only after -- reading it off the
    original, pre-downscale bytes."""
    width, height = 2600, 1800
    image = Image.frombytes("RGB", (width, height), os.urandom(width * height * 3))

    exif = Image.Exif()
    exif.get_ifd(0x8769)[0x9003] = captured_at_str

    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=100, exif=exif)
    raw = buffer.getvalue()
    return base64.b64encode(raw).decode("ascii"), raw


def test_oversized_image_is_downscaled_before_the_vision_call_and_exif_still_reads():
    original_base64, original_raw = _oversized_jpeg_with_exif_base64()
    assert max(Image.open(BytesIO(original_raw)).size) > 2000  # sanity: fixture is actually oversized

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        image_block = next(b for b in body["messages"][0]["content"] if b["type"] == "image")
        captured["media_type"] = image_block["source"]["media_type"]
        captured["data"] = image_block["source"]["data"]
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"theme": "desert-gold", "tags": ["gold"], "aesthetic_score": 0.8, "reasoning": "ok"}
                        ),
                    }
                ]
            },
        )

    analyzer = AnthropicVisionAnalyzer(
        config=VisionAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    pool = MediaPoolService()
    items = [
        MediaAnalyzeAndIngestItem(
            media_ref="oversized-1",
            media_type="image",
            image_base64=original_base64,
            image_media_type="image/jpeg",
        )
    ]

    response = analyze_and_ingest(items, analyzer, pool)

    assert response.analyzed_and_ingested == 1
    assert response.failed == 0

    # the image actually sent to the API is the downscaled one, not the original
    sent_raw = base64.b64decode(captured["data"])
    assert captured["media_type"] == "image/jpeg"
    assert max(Image.open(BytesIO(sent_raw)).size) <= 2000
    assert len(sent_raw) < len(original_raw)

    # captured_at must still come from the ORIGINAL image's EXIF
    ingested_item = pool.list_available()[0]
    assert ingested_item.captured_at is not None
    assert ingested_item.captured_at.strftime("%Y:%m:%d %H:%M:%S") == "2024:01:15 10:30:00"


# -- analyze_and_ingest: video items without a thumbnail ---------------------


def _analyzer_that_must_not_be_called() -> AnthropicVisionAnalyzer:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Claude Vision must not be called for a video with no thumbnail")

    return AnthropicVisionAnalyzer(
        config=VisionAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_video_without_thumbnail_or_path_now_fails_instead_of_placeholding():
    """Behaviour deliberately reversed. Writing a placeholder entry was a
    stopgap for the time before frame extraction existed; it made an
    unanalyzable video indistinguishable from an analyzed one, and hid a
    whole run in which 29 videos arrived without their video_path and every
    single one was reported as a success. See
    test_instagram_video_without_anything_to_analyze.py."""
    pool = MediaPoolService()
    pool.reset()
    items = [
        MediaAnalyzeAndIngestItem(
            media_ref="clip-1",
            media_type="video",
            duration_seconds=15.3,
        )
    ]

    response = analyze_and_ingest(items, _analyzer_that_must_not_be_called(), pool)

    assert response.failed == 1
    assert response.analyzed_and_ingested == 0
    assert "neither video_path nor an image" in response.results[0].error
    assert pool.list_all() == []


def test_video_with_thumbnail_still_goes_through_real_vision_analysis():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"theme": "gym-clip", "tags": ["gym"], "aesthetic_score": 0.82, "reasoning": "ok"}
                        ),
                    }
                ]
            },
        )

    analyzer = AnthropicVisionAnalyzer(
        config=VisionAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    pool = MediaPoolService()
    items = [
        MediaAnalyzeAndIngestItem(
            media_ref="clip-2",
            media_type="video",
            duration_seconds=20.0,
            image_base64=base64.b64encode(b"fake-thumbnail-bytes").decode("ascii"),
            image_media_type="image/jpeg",
        )
    ]

    response = analyze_and_ingest(items, analyzer, pool)

    assert response.failed == 0
    ingested = pool.list_available()[0]
    assert ingested.aesthetic_score == 0.82
    assert ingested.theme == "gym-clip"


def test_a_dated_file_name_carries_a_video_all_the_way_into_its_shoot_day_group():
    """The whole chain in one test, because every link of it was broken at
    some point: n8n sends the Drive file name -> the capture date is read
    from it -> it is stored with source 'filename' -> curate() puts the
    video in that day's bucket, ahead of a later day.

    This is the only path left for a Lightroom-exported video: the
    container's own creation_time holds the export moment, so two clips
    shot weeks apart claim the same afternoon. Both videos below carry
    exactly that broken timestamp -- only the names tell them apart.
    """
    from datetime import datetime, timezone

    from app.instagram_content.captured_at_resolution import CapturedAtSource

    lightroom_export = datetime(2026, 3, 3, 12, 16, 32, tzinfo=timezone.utc)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": json.dumps(
            {"theme": "gym-clip", "tags": ["gym"], "aesthetic_score": 0.5, "reasoning": "ok"}
        )}]})

    analyzer = AnthropicVisionAnalyzer(
        config=VisionAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    pool = MediaPoolService()
    pool.reset()

    response = analyze_and_ingest([
        MediaAnalyzeAndIngestItem(
            media_ref="clip-later", media_type="video", duration_seconds=20.0,
            file_name="2026-02-20_1900_gym.mp4", video_creation_time=lightroom_export,
            image_base64=base64.b64encode(b"thumb").decode("ascii"), image_media_type="image/jpeg",
        ),
        MediaAnalyzeAndIngestItem(
            media_ref="clip-earlier", media_type="video", duration_seconds=20.0,
            file_name="2026-02-14_1830_valencia.mp4", video_creation_time=lightroom_export,
            image_base64=base64.b64encode(b"thumb").decode("ascii"), image_media_type="image/jpeg",
        ),
    ], analyzer, pool)
    assert response.failed == 0

    stored = {i.media_ref: i for i in pool.list_all()}
    assert stored["clip-earlier"].captured_at == datetime(2026, 2, 14, 18, 30, tzinfo=timezone.utc)
    assert stored["clip-earlier"].captured_at_source == CapturedAtSource.filename
    assert stored["clip-later"].captured_at == datetime(2026, 2, 20, 19, 0, tzinfo=timezone.utc)

    groups = curate(pool.list_available())
    assert [g.day for g in groups] == [date(2026, 2, 14), date(2026, 2, 20)], (
        "the earlier shoot day must come first, and the two must not share a bucket"
    )


def test_backfill_gives_older_drafts_their_shoot_day_from_their_own_items():
    """Drafts curated before content_day existed sort as "day unknown" and
    land behind everything dated -- backwards, since they are the oldest in
    the queue. The day is re-derived from their own media items, never
    guessed at; a draft with no dated item honestly keeps None."""
    from datetime import datetime, timezone

    from app.db import SessionLocal
    from app.db_models import InstagramCuratedDraftRow
    from app.instagram_content.captured_at_resolution import CapturedAtSource
    from app.instagram_content.media_pool_models import CuratedDraft

    pool = MediaPoolService()
    pool.reset()
    pool.ingest(MediaPoolIngestRequest(items=[
        MediaPoolItemCreate(
            media_ref="dated", media_type="image", theme="desert-gold", aesthetic_score=0.5,
            captured_at=datetime(2025, 10, 26, 9, 0, tzinfo=timezone.utc),
            captured_at_source=CapturedAtSource.exif,
        ),
        MediaPoolItemCreate(media_ref="undated", media_type="image", theme="desert-gold", aesthetic_score=0.5),
    ]))
    by_ref = {i.media_ref: i for i in pool.list_all()}

    # Two legacy drafts, written the way run_curation() used to: no content_day.
    legacy = [
        CuratedDraft(theme="2025-10-26", reasoning="legacy", media_item_ids=[by_ref["dated"].id]),
        CuratedDraft(theme="desert-gold", reasoning="legacy", media_item_ids=[by_ref["undated"].id]),
    ]
    with SessionLocal() as session:
        for draft in legacy:
            session.add(InstagramCuratedDraftRow(id=str(draft.id), data=draft.model_dump_json()))
        session.commit()

    report = pool.backfill_content_day()
    assert report["filled"] == 1
    assert report["no_dated_items"] == 1

    days = {d.theme: d.content_day for d in pool.list_drafts()}
    assert days["2025-10-26"] == date(2025, 10, 26)
    assert days["desert-gold"] is None, "no dated item means no day, not an invented one"

    assert pool.backfill_content_day()["filled"] == 0, "must be idempotent"
