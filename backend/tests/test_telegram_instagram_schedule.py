"""Two slots a day, and what they refuse to do: fire twice, fire late, or
stack a second card on top of an undecided one."""

from __future__ import annotations

from datetime import date, datetime, timedelta

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
    slot_for,
    waiting_for_a_decision,
)


@pytest.fixture(autouse=True)
def _clean():
    MediaPoolService().reset()
    InstagramContentService().reset()
    yield


def _at(hour: int, minute: int = 0) -> datetime:
    """A time on a day whose slot matches that hour, so the tests read the
    way the schedule behaves rather than depending on today's parity."""
    day = next(d for d in (date(2026, 9, 23), date(2026, 9, 24))
               if slot_for(d).hour == hour)
    return datetime(day.year, day.month, day.day, hour, minute)


def test_one_post_a_day_alternating_feed_and_reel():
    """Two cards a day was the first version; posting twice a day burns the
    backlog and reads as noise."""
    days = [date(2026, 9, 23) + timedelta(days=i) for i in range(6)]
    kinds = [slot_for(day).kind for day in days]

    assert kinds in (["feed", "reel"] * 3, ["reel", "feed"] * 3), "strictly alternating"
    assert slot_for(days[0]) in (FEED_SLOT, REEL_SLOT)


def test_only_todays_slot_is_due_and_only_in_its_grace_window():
    scheduler = PostingScheduler()
    feed_day = next(d for d in (date(2026, 9, 23), date(2026, 9, 24)) if slot_for(d) == FEED_SLOT)
    noon = datetime(feed_day.year, feed_day.month, feed_day.day, 12, 0)

    assert scheduler.due(noon.replace(hour=11, minute=59)) is None
    assert scheduler.due(noon).kind == "feed"
    assert scheduler.due(noon.replace(minute=39)).kind == "feed", "a late start still sends a useful card"
    assert scheduler.due(noon.replace(hour=13, minute=30)) is None, "a passed moment gets no card"
    assert scheduler.due(noon.replace(hour=19)) is None, "the Reel slot belongs to the other day"


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
