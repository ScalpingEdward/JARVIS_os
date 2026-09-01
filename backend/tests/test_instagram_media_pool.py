from __future__ import annotations

import httpx
import pytest

from app.instagram_content.curation import CAROUSEL_IDEAL_MAX_SIZE, CAROUSEL_MIN_SIZE, ELITE_SOLO_THRESHOLD, curate
from app.instagram_content.media_pool_models import FinalizeDraftRequest, MediaPoolIngestRequest, MediaPoolItemCreate
from app.instagram_content.media_pool_service import MediaPoolError, MediaPoolService
from app.instagram_content.models import ContentStatus, PostFormat
from app.instagram_content.publisher import N8nInstagramPublisher
from app.instagram_content.service import InstagramContentError, InstagramContentService


def _image_create(ref, theme="desert-gold", score=0.75):
    return MediaPoolItemCreate(media_ref=ref, media_type="image", theme=theme, aesthetic_score=score)


def _video_create(ref, theme="desert-gold", score=0.75, duration=25.0):
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


def test_curate_always_puts_a_video_alone():
    from app.instagram_content.media_pool_models import MediaPoolItem

    video = MediaPoolItem(**_video_create("clip", score=0.5).model_dump())
    images = [MediaPoolItem(**_image_create(f"img-{i}", score=0.5).model_dump()) for i in range(3)]
    groups = curate([video, *images])

    video_groups = [g for g in groups if any(m.media_type == "video" for m in g.media_items)]
    assert len(video_groups) == 1
    assert len(video_groups[0].media_items) == 1


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
