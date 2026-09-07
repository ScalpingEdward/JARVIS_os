from __future__ import annotations

from fastapi.testclient import TestClient

from app.instagram_content.curation import DEFAULT_LOW_WATER_MARK, analyze_gaps
from app.instagram_content.media_pool_models import MediaPoolItem, MediaPoolItemCreate
from app.instagram_content.media_pool_service import MediaPoolService
from app.instagram_content.platform_strategy import platform_strategy_store
from app.main import app

api_client = TestClient(app)


def _image(ref, theme="desert-gold", score=0.5, tags=None):
    return MediaPoolItem(**MediaPoolItemCreate(
        media_ref=ref, media_type="image", theme=theme, aesthetic_score=score,
        tags=tags or [],
    ).model_dump())


def setup_function(_):
    platform_strategy_store.reset()


# -- analyze_gaps() unit tests: pure read, no side effects -------------------

def test_no_gap_when_theme_has_enough_for_a_full_carousel():
    items = [_image(f"img-{i}") for i in range(3)]  # == carousel_min_size
    report = analyze_gaps(items)
    assert report.theme_gaps == []


def test_gap_reported_when_theme_is_short_of_the_minimum():
    items = [_image(f"img-{i}") for i in range(2)]  # one short of min (3)
    report = analyze_gaps(items)
    assert len(report.theme_gaps) == 1
    gap = report.theme_gaps[0]
    assert gap.theme == "desert-gold"
    assert gap.available_count == 2
    assert gap.needed_for_carousel == 1


def test_gap_carries_tags_as_a_style_hint():
    items = [
        _image("img-0", tags=["gold", "desk"]),
        _image("img-1", tags=["gold", "candlelight"]),
    ]
    report = analyze_gaps(items)
    assert report.theme_gaps[0].sample_tags == ["candlelight", "desk", "gold"]
    assert set(report.theme_gaps[0].sample_media_refs) == {"img-0", "img-1"}


def test_a_leftover_remainder_above_a_full_batch_is_still_a_gap():
    """13 same-theme images: 10 (ideal max) become one carousel, 3 remain --
    exactly at carousel_min_size, so that remainder is NOT a gap. 11 images
    leaves a remainder of 1, which IS a gap."""
    eleven = [_image(f"img-{i}") for i in range(11)]
    report = analyze_gaps(eleven)
    assert len(report.theme_gaps) == 1
    assert report.theme_gaps[0].available_count == 1

    thirteen = [_image(f"img-{i}") for i in range(13)]
    report = analyze_gaps(thirteen)
    assert report.theme_gaps == []


def test_used_items_are_excluded_from_the_pool_before_counting_gaps():
    items = [_image(f"img-{i}") for i in range(3)]  # exactly enough for a carousel
    items[0].used = True
    report = analyze_gaps(items)
    assert report.available_count == 2
    assert report.theme_gaps[0].available_count == 2
    assert report.theme_gaps[0].needed_for_carousel == 1


def test_videos_are_never_a_gap():
    video = MediaPoolItem(**MediaPoolItemCreate(
        media_ref="clip", media_type="video", theme="desert-gold",
        aesthetic_score=0.5, duration_seconds=20.0,
    ).model_dump())
    report = analyze_gaps([video])
    assert report.theme_gaps == []


def test_elite_solo_items_are_never_a_gap():
    strong = _image("hero", score=platform_strategy_store.current().elite_solo_threshold)
    report = analyze_gaps([strong])
    assert report.theme_gaps == []


def test_multiple_themes_reported_independently():
    items = [_image("a-0", theme="a"), _image("b-0", theme="b"), _image("b-1", theme="b")]
    report = analyze_gaps(items)
    themes = {g.theme: g for g in report.theme_gaps}
    assert themes["a"].available_count == 1
    assert themes["b"].available_count == 2


def test_pool_low_uses_the_configured_mark():
    items = [_image(f"img-{i}", theme=f"t{i}") for i in range(5)]
    assert analyze_gaps(items, low_water_mark=10).pool_low
    assert not analyze_gaps(items, low_water_mark=3).pool_low


def test_default_low_water_mark_is_used_when_not_specified():
    items = [_image(f"img-{i}", theme=f"t{i}") for i in range(DEFAULT_LOW_WATER_MARK)]
    assert analyze_gaps(items).pool_low  # exactly at the mark


def test_empty_pool_reports_low_and_no_gaps():
    report = analyze_gaps([])
    assert report.available_count == 0 and report.pool_low and report.theme_gaps == []


def test_a_research_driven_strategy_change_is_reflected_live():
    """Same live-store discipline as curation.py and moderation.py -- a
    platform_strategy_store.apply() takes effect without a code change."""
    from app.instagram_content.platform_strategy import PlatformStrategy

    items = [_image(f"img-{i}") for i in range(4)]
    assert analyze_gaps(items).theme_gaps == []  # 4 >= default min (3)

    platform_strategy_store.apply(PlatformStrategy(carousel_min_size=5))
    report = analyze_gaps(items)
    assert report.theme_gaps and report.theme_gaps[0].needed_for_carousel == 1


# -- service + API -------------------------------------------------------

def test_service_content_gaps_reads_only_available_items():
    from app.instagram_content.media_pool_models import MediaPoolIngestRequest

    service = MediaPoolService()
    service.ingest(MediaPoolIngestRequest(items=[
        MediaPoolItemCreate(media_ref="a", media_type="image", theme="x", aesthetic_score=0.5),
        MediaPoolItemCreate(media_ref="b", media_type="image", theme="x", aesthetic_score=0.5),
    ]))
    report = service.content_gaps()
    assert report.available_count == 2
    assert report.theme_gaps[0].theme == "x"


def test_gaps_endpoint_is_read_only():
    import app.instagram_content.media_pool_service as pool_module
    from app.instagram_content.media_pool_models import MediaPoolIngestRequest

    pool_module.media_pool_service.reset()
    pool_module.media_pool_service.ingest(MediaPoolIngestRequest(items=[
        MediaPoolItemCreate(media_ref="a", media_type="image", theme="x", aesthetic_score=0.5),
    ]))
    resp_before = api_client.get("/v1/instagram/media-pool", params={"available_only": True})
    resp = api_client.get("/v1/instagram/media-pool/gaps")
    resp_after = api_client.get("/v1/instagram/media-pool", params={"available_only": True})
    assert resp.status_code == 200
    assert resp_before.json() == resp_after.json(), "calling gaps must not reserve or change anything"


def test_gaps_endpoint_shape():
    resp = api_client.get("/v1/instagram/media-pool/gaps")
    body = resp.json()
    assert set(body) == {"available_count", "theme_gaps", "pool_low", "low_water_mark"}
