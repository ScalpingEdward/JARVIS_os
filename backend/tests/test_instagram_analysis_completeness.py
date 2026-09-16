"""The single definition of "this item was never really analyzed", plus the
re-analysis path it unlocks.

Background: videos have no frame-extraction step yet, so they were ingested
with a placeholder theme, an empty tag list and no captured_at. The n8n
pre-filter dropped every media_ref already in the pool, and the backend
skipped every known media_ref too -- so those placeholder rows could never
be revisited. 30 of them sat in the live pool that way.
"""

from datetime import datetime, timezone
from uuid import uuid4

from app.db import SessionLocal
from app.db_models import InstagramMediaPoolItemRow
from app.instagram_content.analysis_completeness import (
    analysis_incompleteness_reasons,
    analysis_is_complete,
)
from app.instagram_content.captured_at_resolution import CapturedAtSource
from app.instagram_content.media_pool_models import (
    MediaPoolIngestRequest,
    MediaPoolItem,
    MediaPoolItemCreate,
)
from app.instagram_content.media_pool_service import MediaPoolService
from app.instagram_content.models import MediaType


def _real_image(media_ref: str = "drive-image-1", **overrides) -> MediaPoolItemCreate:
    payload = dict(
        media_ref=media_ref,
        media_type=MediaType.image,
        theme="trading-desk-setup",
        tags=["desk", "charts"],
        aesthetic_score=0.71,
        captured_at=datetime(2026, 9, 14, 8, 30, tzinfo=timezone.utc),
        captured_at_source=CapturedAtSource.exif,
    )
    payload.update(overrides)
    if payload.get("captured_at") is None:
        # the model refuses a source without a timestamp, and vice versa
        payload["captured_at_source"] = None
    return MediaPoolItemCreate(**payload)


def _placeholder_video(media_ref: str = "drive-video-1") -> MediaPoolItemCreate:
    """Exactly what analyze_and_ingest writes for a video it cannot look at."""
    return MediaPoolItemCreate(
        media_ref=media_ref,
        media_type=MediaType.video,
        theme="video",
        tags=[],
        aesthetic_score=0.6,
        duration_seconds=9.305,
        captured_at=None,
    )


# -- the criterion ----------------------------------------------------------


def test_a_fully_analyzed_image_is_complete():
    assert analysis_incompleteness_reasons(_real_image()) == []
    assert analysis_is_complete(_real_image()) is True


def test_the_placeholder_video_is_incomplete_for_all_three_reasons():
    reasons = analysis_incompleteness_reasons(_placeholder_video())
    assert len(reasons) == 3
    assert any("tags" in r for r in reasons)
    assert any("captured_at" in r for r in reasons)
    assert any("placeholder" in r for r in reasons)


def test_each_rule_fires_on_its_own():
    assert analysis_incompleteness_reasons(_real_image(tags=[])) == ["tags are empty"]
    assert analysis_incompleteness_reasons(_real_image(captured_at=None)) == ["captured_at is missing"]
    assert analysis_incompleteness_reasons(_real_image(theme="unknown")) == [
        "theme is a placeholder ('unknown')"
    ]


def test_theme_equal_to_the_media_type_is_a_placeholder_whatever_the_type():
    """The rule is generic on purpose -- keyed on theme == media_type rather
    than the literal string "video", so a future media type needs no change."""
    assert analysis_incompleteness_reasons(_real_image(theme="image")) == [
        "theme is a placeholder ('image')"
    ]
    assert analysis_incompleteness_reasons(_real_image(theme="  IMAGE  ")) == [
        "theme is a placeholder ('  IMAGE  ')"
    ]


def test_a_video_with_a_real_analysis_is_complete():
    """Completeness is about the analysis, not the media type -- once frame
    extraction exists, videos pass without any change here."""
    analyzed_video = MediaPoolItemCreate(
        media_ref="drive-video-2",
        media_type=MediaType.video,
        theme="gym-mirror-selfie",
        tags=["gym", "motion"],
        aesthetic_score=0.64,
        duration_seconds=12.0,
        captured_at=datetime(2026, 9, 15, 6, 0, tzinfo=timezone.utc),
        captured_at_source=CapturedAtSource.video_metadata,
    )
    assert analysis_is_complete(analyzed_video) is True


def test_media_pool_item_exposes_analysis_complete_in_its_json():
    """The n8n workflow reads this field instead of re-deriving the rule."""
    incomplete = MediaPoolItem(**_placeholder_video().model_dump())
    complete = MediaPoolItem(**_real_image().model_dump())

    assert incomplete.analysis_complete is False
    assert complete.analysis_complete is True
    assert '"analysis_complete":false' in incomplete.model_dump_json().replace(" ", "")
    assert '"analysis_complete":true' in complete.model_dump_json().replace(" ", "")


# -- the re-analysis path ---------------------------------------------------


def test_reingesting_an_incomplete_item_updates_it_instead_of_skipping_it():
    service = MediaPoolService()
    service.reset()

    first = service.ingest(MediaPoolIngestRequest(items=[_placeholder_video()]))
    assert (first.ingested, first.updated_incomplete, first.skipped_duplicates) == (1, 0, 0)
    assert service.list_all()[0].analysis_complete is False

    real = MediaPoolItemCreate(
        media_ref="drive-video-1",
        media_type=MediaType.video,
        theme="gym-mirror-selfie",
        tags=["gym", "motion"],
        aesthetic_score=0.82,
        duration_seconds=9.305,
        captured_at=datetime(2026, 9, 15, 6, 0, tzinfo=timezone.utc),
        captured_at_source=CapturedAtSource.video_metadata,
    )
    second = service.ingest(MediaPoolIngestRequest(items=[real]))

    assert (second.ingested, second.updated_incomplete, second.skipped_duplicates) == (0, 1, 0)
    assert len(service.list_all()) == 1, "the update must not insert a second row"
    after = service.list_all()[0]
    assert after.analysis_complete is True
    assert after.theme == "gym-mirror-selfie"
    assert after.tags == ["gym", "motion"]
    assert after.aesthetic_score == 0.82


def test_an_update_preserves_identity_reservation_usage_and_the_trim_window():
    """The decisive guarantee: all 30 placeholder videos in the live pool are
    reserved in a draft. Re-analyzing them must improve the row the draft
    already points at, never detach it or hand it a new id."""
    service = MediaPoolService()
    service.reset()
    service.ingest(MediaPoolIngestRequest(items=[_placeholder_video()]))

    original = service.list_all()[0]
    draft_id, candidate_id = uuid4(), uuid4()
    used_at = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    with_state = original.model_copy(update={
        "reserved_in_draft_id": draft_id,
        "used": True,
        "used_in_candidate_id": candidate_id,
        "used_at": used_at,
        "recommended_trim_start_seconds": 2.0,
        "recommended_trim_end_seconds": 8.0,
        "trim_reasoning": "best motion window",
    })
    with SessionLocal() as session:
        row = session.get(InstagramMediaPoolItemRow, str(original.id))
        row.data = with_state.model_dump_json()
        session.commit()

    service.ingest(MediaPoolIngestRequest(items=[MediaPoolItemCreate(
        media_ref="drive-video-1",
        media_type=MediaType.video,
        theme="gym-mirror-selfie",
        tags=["gym"],
        aesthetic_score=0.82,
        duration_seconds=9.305,
        captured_at=datetime(2026, 9, 15, 6, 0, tzinfo=timezone.utc),
        captured_at_source=CapturedAtSource.video_metadata,
    )]))

    after = service.list_all()[0]
    assert after.id == original.id
    assert after.media_ref == "drive-video-1"
    assert after.reserved_in_draft_id == draft_id
    assert after.used is True
    assert after.used_in_candidate_id == candidate_id
    assert after.used_at == used_at
    assert after.recommended_trim_start_seconds == 2.0
    assert after.recommended_trim_end_seconds == 8.0
    assert after.trim_reasoning == "best motion window"
    assert after.theme == "gym-mirror-selfie"


def test_a_complete_item_is_still_skipped_as_a_duplicate():
    service = MediaPoolService()
    service.reset()
    service.ingest(MediaPoolIngestRequest(items=[_real_image()]))

    response = service.ingest(MediaPoolIngestRequest(items=[
        _real_image(theme="something-else", tags=["other"], aesthetic_score=0.1)
    ]))

    assert (response.ingested, response.updated_incomplete, response.skipped_duplicates) == (0, 0, 1)
    assert service.list_all()[0].theme == "trading-desk-setup", "a real analysis is never overwritten"


def test_a_placeholder_does_not_overwrite_another_placeholder():
    """Until frame extraction exists, the workflow re-feeds these videos every
    run. That must stay a no-op rather than churning analyzed_at each time."""
    service = MediaPoolService()
    service.reset()
    service.ingest(MediaPoolIngestRequest(items=[_placeholder_video()]))
    before = service.list_all()[0].analyzed_at

    response = service.ingest(MediaPoolIngestRequest(items=[_placeholder_video()]))

    assert (response.ingested, response.updated_incomplete, response.skipped_duplicates) == (0, 0, 1)
    assert service.list_all()[0].analyzed_at == before
