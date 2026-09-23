"""Brano's own pick beats the score, and the score says why it is what it is."""

from __future__ import annotations

import pytest

from app.instagram_content.curation import curate
from app.instagram_content.media_pool_models import MediaPoolIngestRequest, MediaPoolItemCreate
from app.instagram_content.media_pool_service import MediaPoolError, MediaPoolService, media_pool_service


def _create(ref, score=0.35, reasoning=""):
    return MediaPoolItemCreate(media_ref=ref, media_type="image", theme="cigars",
                               aesthetic_score=score, analysis_reasoning=reasoning)


@pytest.fixture(autouse=True)
def _clean():
    MediaPoolService().reset()
    yield


def test_the_reason_for_a_score_is_kept_not_thrown_away():
    """Without it a 0.35 is a verdict nobody can argue with, and the fix --
    crop the cluttered edge -- stays invisible."""
    media_pool_service.ingest(MediaPoolIngestRequest(items=[
        _create("photo-1", reasoning="Strong subject, but a plastic bag and a stranger's leg clutter the edges.")
    ]))
    assert media_pool_service.list_all()[0].analysis_reasoning.startswith("Strong subject")


def test_a_favourite_carries_a_post_alone_however_it_scored():
    media_pool_service.ingest(MediaPoolIngestRequest(items=[_create("photo-1", score=0.35)]))

    assert curate(media_pool_service.list_all()) == [], "0.35 alone is not a post"

    media_pool_service.set_favorite("photo-1")
    groups = curate(media_pool_service.list_all())

    assert len(groups) == 1
    assert [i.media_ref for i in groups[0].media_items] == ["photo-1"]
    assert "favourite" in groups[0].reasoning
    assert "0.35" in groups[0].reasoning, "the real score stays visible, it is not rewritten"


def test_a_favourite_can_be_taken_back():
    media_pool_service.ingest(MediaPoolIngestRequest(items=[_create("photo-1")]))
    media_pool_service.set_favorite("photo-1")
    assert media_pool_service.set_favorite("photo-1", False).favorite is False
    assert curate(media_pool_service.list_all()) == []


def test_marking_something_that_is_not_in_the_pool_is_refused():
    with pytest.raises(MediaPoolError, match="No pool item"):
        media_pool_service.set_favorite("never-seen")


def test_a_favourite_is_never_set_by_an_analysis():
    """Only Brano sets it -- an ingest must not be able to declare its own
    item a favourite and jump the quality bar."""
    assert "favorite" not in MediaPoolItemCreate.model_fields
