"""The card arrives when the post should go out, not when someone asks.

One post a day at most, and which post is never a matter of the calendar:
the queue is shoot-day order, oldest day first, and a day is exhausted
before the next begins. Whether that next post is a Reel or a carousel only
decides the hour -- evening for a Reel, where Reels reach people who do not
follow the account yet, midday for a feed post. Alternating by day was the
version before this one, and it let a Reel from a later shoot overtake
photos from the day before it.

Deliberately simple: a minute tick, a local clock, and one memory of what
already fired today. A slot missed because the laptop was asleep is not
fired late -- a card at 02:00 for the midday slot would be worse than no
card, and the next day's slot comes anyway.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.instagram_content.media_pool_service import media_pool_service
from app.instagram_content.models import ContentStatus
from app.instagram_content.service import instagram_content_service

from .service import TelegramInstagramError, telegram_instagram_service

log = logging.getLogger(__name__)
# Uvicorn shows only its own INFO lines; without a handler of its own this
# module's INFO went nowhere, and on 2026-10-15 a 19:00 slot left no trace at
# all -- not whether it fired, failed or was slept through.
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s posting schedule: %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False


def alert(message: str) -> None:
    """Tell Brano on Telegram that a slot did not produce a card, and why.
    Module-level so tests can replace it; a delivery failure only logs."""
    telegram_instagram_service._safe_send(message)

#: How late a slot may still fire. Started 40 minutes after the slot (a
#: reboot, a long ingest run), the card is still useful; an hour later it
#: is a card for a moment that has passed.
_GRACE_MINUTES = 40
_TICK_SECONDS = 60


@dataclass(frozen=True)
class Slot:
    hour: int
    minute: int
    kind: str  # "feed" or "reel"


FEED_SLOT = Slot(12, 0, "feed")
REEL_SLOT = Slot(19, 0, "reel")


def next_draft_kind() -> str | None:
    """The sort of the next draft in the queue, or None when nothing waits.

    The queue's order is the shoot day, oldest first, and one day is
    exhausted before the next begins. That order decides what goes out --
    not an alternation between sorts: alternating by calendar meant a Reel
    from a later shoot could jump ahead of photos from the day before it,
    and the feed stopped telling the days in the order they happened.
    """
    drafts = media_pool_service.list_drafts(pending_only=True)
    if not drafts:
        return None
    return telegram_instagram_service._draft_kind(drafts[0])


def posted_today(today: date) -> bool:
    return any(
        c.status == ContentStatus.posted and c.updated_at.date() == today
        for c in instagram_content_service.list_all()
    )


def next_slot(slots: tuple[Slot, Slot] = (FEED_SLOT, REEL_SLOT)) -> Slot:
    """When today's card is due: the time that belongs to the sort of the
    next draft. A Reel is worth the evening, a feed post the midday hour --
    but which of them comes next is the queue's decision, not the clock's."""
    feed, reel = slots
    return reel if next_draft_kind() == "reel" else feed


def _timezone() -> ZoneInfo:
    return ZoneInfo(os.getenv("AURON_TIMEZONE", "Europe/Berlin"))


def card_sent_today(today: date) -> bool:
    """A card already went out today (whatever became of it). Survives a restart
    of the API, which the in-memory record of fired slots does not."""
    return any(c.created_at.date() == today for c in instagram_content_service.list_all())


def waiting_for_a_decision() -> bool:
    """A card is already on the phone and undecided. Sending another one
    would stack decisions Brano has to work through backwards, and the
    second card's photos would be reserved before the first was answered."""
    return any(c.status == ContentStatus.proposed for c in instagram_content_service.list_all())


class PostingScheduler:
    def __init__(self, slots: tuple[Slot, Slot] = (FEED_SLOT, REEL_SLOT)) -> None:
        self.slots = slots
        self._fired: dict[tuple[date, int, int], bool] = {}
        self._task: asyncio.Task | None = None
        self._last_error: tuple[date, str] | None = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def fired_slots(self) -> list[tuple[date, int, int]]:
        return sorted(self._fired)

    def due(self, now: datetime) -> Slot | None:
        slot = next_slot(self.slots)
        if self._fired.get((now.date(), slot.hour, slot.minute)):
            return None
        # One post a day, whatever the clock says: a Reel that becomes due
        # at 19:00 because a photo went out at 12:00 would make two.
        if posted_today(now.date()):
            return None
        minutes_late = (now.hour - slot.hour) * 60 + (now.minute - slot.minute)
        return slot if 0 <= minutes_late <= _GRACE_MINUTES else None

    def missed(self, now: datetime) -> Slot | None:
        """Today's slot is past its grace and nothing went out: AURON was not
        running then (laptop asleep or off). Reported once, never fired late."""
        slot = next_slot(self.slots)
        key = (now.date(), slot.hour, slot.minute)
        if self._fired.get(key) or posted_today(now.date()) or card_sent_today(now.date()):
            return None
        minutes_late = (now.hour - slot.hour) * 60 + (now.minute - slot.minute)
        if minutes_late <= _GRACE_MINUTES:
            return None
        self._fired[key] = True
        return slot

    def fire(self, slot: Slot, now: datetime) -> str:
        """Send one card for this slot. Returns what happened, for the log.
        A slot is marked as fired either way: an empty queue is not a reason
        to retry every minute until midnight."""
        self._fired[(now.date(), slot.hour, slot.minute)] = True
        when = f"{slot.hour:02d}:{slot.minute:02d}"
        if waiting_for_a_decision():
            alert(f"{when}: keine neue Karte – die letzte wartet noch auf deine Entscheidung.")
            return "skipped: a card is still waiting for a decision"
        try:
            # No kind filter: the head of the queue is the post that is due,
            # and the slot's time was chosen from that same head.
            result = telegram_instagram_service.finalize_next_and_notify()
        except TelegramInstagramError as exc:
            alert(f"{when}: keine Karte verschickt – {exc}")
            return f"nothing sent: {exc}"
        return f"sent candidate {result.candidate_id}"

    async def _run(self) -> None:
        while True:
            try:
                now = datetime.now(_timezone())
                slot = self.due(now)
                if slot is not None:
                    outcome = await asyncio.to_thread(self.fire, slot, now)
                    log.info("slot %02d:%02d (%s): %s", slot.hour, slot.minute, slot.kind, outcome)
                missed = await asyncio.to_thread(self.missed, now)
                if missed is not None:
                    log.warning("slot %02d:%02d (%s) missed: AURON was not running then", missed.hour, missed.minute, missed.kind)
                    kind = "Reel" if missed.kind == "reel" else "Beitrag"
                    await asyncio.to_thread(alert, f"{missed.hour:02d}:{missed.minute:02d}: {kind} verpasst – AURON lief da nicht "
                                                   "(Laptop schlief oder war aus). Nächste Chance morgen.")
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 -- a bad tick must not end the schedule
                log.warning("tick failed: %s", exc)
                key = (date.today(), str(exc))
                if key != self._last_error:  # once a day per error, not once a minute
                    self._last_error = key
                    await asyncio.to_thread(alert, f"Fehler im Instagram-Zeitplan: {exc}")
            await asyncio.sleep(_TICK_SECONDS)

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())
        log.info("posting schedule started, one a day alternating: %s", ", ".join(
            f"{s.hour:02d}:{s.minute:02d} {s.kind}" for s in self.slots))

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


posting_scheduler = PostingScheduler()
