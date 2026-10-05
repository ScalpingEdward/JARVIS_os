"""Taking back a post that no longer exists on Instagram.

Brano deleted the first real Reel from his account right after the test
that proved the publish path works. The video stayed marked used: a post
that is gone, blocking footage that is free, with nothing able to reclaim
it -- release only ever happened when a publish failed.
"""

from __future__ import annotations

import pytest

from app.instagram_content.media_pool_models import MediaPoolIngestRequest, MediaPoolItemCreate
from app.instagram_content.media_pool_service import MediaPoolService, media_pool_service
from app.instagram_content.models import (
    ContentCandidateCreate,
    ContentStatus,
    MediaItem,
)
from app.instagram_content.service import InstagramContentError, InstagramContentService


@pytest.fixture(autouse=True)
def _clean():
    MediaPoolService().reset()
    InstagramContentService().reset()
    yield


def _posted_candidate(service: InstagramContentService):
    media_pool_service.ingest(MediaPoolIngestRequest(items=[MediaPoolItemCreate(
        media_ref="clip", media_type="video", theme="t", aesthetic_score=0.8,
        duration_seconds=20.0)]))
    candidate = service.propose(ContentCandidateCreate(
        media_items=[MediaItem(media_ref="clip", media_type="video", aesthetic_score=0.8,
                              duration_seconds=20.0)],
        caption_draft="Quiet. #trading #discipline #mindset"))
    draft = media_pool_service.run_curation()[0]
    media_pool_service.mark_finalized(draft.id, candidate.id)
    item = service.get(candidate.id)
    item.status = ContentStatus.posted
    item.published_media_id = "17909762832554719"
    service._save_candidate(item)
    return item


def test_a_post_deleted_on_instagram_gives_its_media_back():
    service = InstagramContentService()
    candidate = _posted_candidate(service)

    result = service.withdraw_posted(candidate.id, "deleted on Instagram")

    assert result.status == ContentStatus.rejected
    assert [i for i in media_pool_service.list_all() if i.media_ref == "clip"][0].used is False


def test_the_log_says_it_went_out_and_came_back():
    """Not quietly pretending it never posted: the media_id stays readable,
    because something was on that account and someone may ask what."""
    service = InstagramContentService()
    candidate = _posted_candidate(service)

    result = service.withdraw_posted(candidate.id, "deleted on Instagram")

    line = [l for l in result.audit_log if "Withdrawn after posting" in l]
    assert line and "17909762832554719" in line[0]


def test_a_candidate_that_was_never_posted_cannot_be_withdrawn():
    service = InstagramContentService()
    candidate = service.propose(ContentCandidateCreate(
        media_items=[MediaItem(media_ref="x", media_type="image", aesthetic_score=0.8)],
        caption_draft="Quiet. #trading #discipline #mindset"))

    with pytest.raises(InstagramContentError):
        service.withdraw_posted(candidate.id, "oops")
