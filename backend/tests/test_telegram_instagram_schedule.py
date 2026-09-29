"""Two slots a day, and what they refuse to do: fire twice, fire late, or
stack a second card on top of an undecided one."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.instagram_content.media_pool_models import MediaPoolIngestRequest, MediaPoolItemCreate
from app.instagram_content.media_pool_service import MediaPoolService, media_pool_service
from app.instagram_content.models import ContentCandidateCreate, MediaItem
from app.instagram_content.service import InstagramContentService
from app.telegram_instagram import schedule as schedule_module
from app.telegram_instagram.schedule import (
    FEED_SLOT,
    REEL_SLOT,
    PostingScheduler,
    Slot,
    waiting_for_a_decision,
)


@pytest.fixture(autouse=True)
def _clean():
    MediaPoolService().reset()
    InstagramContentService().reset()
    yield


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, 23, hour, minute)


def _posted(kind: str, when: datetime):
    """A post that really went out, of this sort, at this time."""
    from app.instagram_content.models import ContentCandidateCreate, ContentDecision

    service = InstagramContentService()
    media = ([MediaItem(media_ref=f"clip-{when.isoformat()}", media_type="video",
                        aesthetic_score=0.8, duration_seconds=20.0)] if kind == "reel"
             else [MediaItem(media_ref=f"pic-{when.isoformat()}", media_type="image", aesthetic_score=0.8)])
    candidate = service.propose(ContentCandidateCreate(
        media_items=media, caption_draft="Quiet. #trading #discipline #mindset"))
    service.decide(candidate.id, ContentDecision(approved=True, reason="test"))
    from app.db import SessionLocal
    from app.db_models import InstagramContentCandidateRow
    from app.instagram_content.models import ContentCandidate, ContentStatus

    with SessionLocal() as session:
        row = session.get(InstagramContentCandidateRow, str(candidate.id))
        item = ContentCandidate.model_validate_json(row.data)
        item.status = ContentStatus.posted
        item.updated_at = when
        row.status = item.status.value
        row.data = item.model_dump_json()
        session.commit()
    return candidate


def test_the_next_sort_follows_what_was_really_posted():
    """Calendar parity dropped a whole sort whenever its day was skipped: a
    Reel day spent waiting for an undecided card meant the next Reel came
    two days later, while the feed kept its turn."""
    from app.telegram_instagram.schedule import next_slot

    assert next_slot() == FEED_SLOT, "nothing posted yet -- start with a feed post"

    _posted("feed", datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc))
    assert next_slot() == REEL_SLOT

    _posted("reel", datetime(2026, 9, 21, 19, 0, tzinfo=timezone.utc))
    assert next_slot() == FEED_SLOT


def test_a_skipped_day_postpones_the_sort_instead_of_losing_it():
    from app.telegram_instagram.schedule import next_slot

    _posted("feed", datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc))
    scheduler = PostingScheduler()

    # The Reel day passes with a card still open: nothing is sent.
    assert next_slot() == REEL_SLOT
    # Two days later the Reel is still the one that is due.
    assert scheduler.due(datetime(2026, 9, 23, 19, 0)).kind == "reel"


def test_only_one_post_a_day_even_when_the_other_sort_is_due():
    from datetime import timezone as tz

    today = datetime.now(tz.utc)
    _posted("feed", today)
    scheduler = PostingScheduler()

    assert scheduler.due(datetime(today.year, today.month, today.day, 19, 0)) is None


def test_a_fired_slot_does_not_fire_again_the_same_day_but_does_the_next(monkeypatch):
    scheduler = PostingScheduler()
    monkeypatch.setattr(schedule_module, "waiting_for_a_decision", lambda: True)

    scheduler.fire(scheduler.due(_at(12, 0)), _at(12, 0))

    noon = _at(12, 0)
    assert scheduler.due(noon.replace(minute=5)) is None
    assert scheduler.due(noon.replace(hour=19)) is None, "this day has no second slot"
    in_two_days = noon.date() + timedelta(days=2)
    assert scheduler.due(datetime(in_two_days.year, in_two_days.month, in_two_days.day, 12, 0)).kind == "feed"


def test_a_slot_with_an_undecided_card_open_sends_nothing(monkeypatch):
    monkeypatch.setattr(schedule_module, "waiting_for_a_decision", lambda: True)
    sent: list = []
    monkeypatch.setattr(schedule_module.telegram_instagram_service, "finalize_next_and_notify",
                        lambda **kwargs: sent.append(kwargs))

    outcome = PostingScheduler().fire(Slot(12, 0, "feed"), _at(12, 0))

    assert "still waiting for a decision" in outcome
    assert sent == []


def test_the_evening_slot_asks_for_a_reel_and_the_midday_slot_for_a_feed_post(monkeypatch):
    monkeypatch.setattr(schedule_module, "waiting_for_a_decision", lambda: False)
    asked: list = []

    class _Result:
        candidate_id = "x"

    monkeypatch.setattr(schedule_module.telegram_instagram_service, "finalize_next_and_notify",
                        lambda **kwargs: (asked.append(kwargs["kind"]), _Result())[1])

    scheduler = PostingScheduler()
    scheduler.fire(Slot(12, 0, "feed"), _at(12, 0))
    scheduler.fire(Slot(19, 0, "reel"), _at(19, 0))

    assert asked == ["feed", "reel"]


def test_an_empty_queue_is_reported_and_not_retried_every_minute(monkeypatch):
    monkeypatch.setattr(schedule_module, "waiting_for_a_decision", lambda: False)
    scheduler = PostingScheduler()

    outcome = scheduler.fire(Slot(19, 0, "reel"), _at(19, 0))

    assert "nothing sent" in outcome
    assert scheduler.due(_at(19, 10)) is None


def test_waiting_for_a_decision_sees_a_real_proposed_candidate():
    assert waiting_for_a_decision() is False
    InstagramContentService().propose(ContentCandidateCreate(
        media_items=[MediaItem(media_ref="x", media_type="image", aesthetic_score=0.7)],
        caption_draft="Quiet. #trading #discipline #mindset",
    ))
    assert waiting_for_a_decision() is True


def test_a_single_video_draft_is_a_reel_and_the_rest_are_feed_posts():
    from app.telegram_instagram.service import TelegramInstagramService

    media_pool_service.ingest(MediaPoolIngestRequest(items=[
        MediaPoolItemCreate(media_ref="clip", media_type="video", theme="gym",
                            aesthetic_score=0.8, duration_seconds=20.0),
        *[MediaPoolItemCreate(media_ref=f"pic-{i}", media_type="image", theme="beach",
                              aesthetic_score=0.8) for i in range(3)],
    ]))
    drafts = media_pool_service.run_curation()
    kinds = {TelegramInstagramService._draft_kind(d) for d in drafts}

    assert kinds <= {"reel", "feed"}
    solo_video = [d for d in drafts if len(d.media_item_ids) == 1
                  and media_pool_service.draft_media_items(d)[0].media_type == "video"]
    for draft in solo_video:
        assert TelegramInstagramService._draft_kind(draft) == "reel"


def test_the_schedule_says_whether_it_is_actually_running():
    """"Enabled" in an env file is a claim; a stopped task is the fact."""
    scheduler = PostingScheduler()
    assert scheduler.is_running is False
