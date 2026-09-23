"""The card arrives when the post should go out, not when someone asks.

Two slots a day, from the 2026 data: a Reel in the evening, where Reels
reach people who do not follow the account yet, and a feed post at midday.
The card is the start of Brano's own posting minute -- files, caption,
music picked in the app -- so it has to land shortly before the time the
post should be up, not hours earlier.

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

from app.instagram_content.models import ContentStatus
from app.instagram_content.service import instagram_content_service

from .service import TelegramInstagramError, telegram_instagram_service

log = logging.getLogger(__name__)

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


DEFAULT_SLOTS = (Slot(12, 0, "feed"), Slot(19, 0, "reel"))


def _timezone() -> ZoneInfo:
    return ZoneInfo(os.getenv("AURON_TIMEZONE", "Europe/Berlin"))


def waiting_for_a_decision() -> bool:
    """A card is already on the phone and undecided. Sending another one
    would stack decisions Brano has to work through backwards, and the
    second card's photos would be reserved before the first was answered."""
    return any(c.status == ContentStatus.proposed for c in instagram_content_service.list_all())


class PostingScheduler:
    def __init__(self, slots: tuple[Slot, ...] = DEFAULT_SLOTS) -> None:
        self.slots = slots
        self._fired: dict[tuple[date, int, int], bool] = {}
        self._task: asyncio.Task | None = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def fired_slots(self) -> list[tuple[date, int, int]]:
        return sorted(self._fired)

    def due(self, now: datetime) -> Slot | None:
        for slot in self.slots:
            if self._fired.get((now.date(), slot.hour, slot.minute)):
                continue
            minutes_late = (now.hour - slot.hour) * 60 + (now.minute - slot.minute)
            if 0 <= minutes_late <= _GRACE_MINUTES:
                return slot
        return None

    def fire(self, slot: Slot, now: datetime) -> str:
        """Send one card for this slot. Returns what happened, for the log.
        A slot is marked as fired either way: an empty queue is not a reason
        to retry every minute until midnight."""
        self._fired[(now.date(), slot.hour, slot.minute)] = True
        if waiting_for_a_decision():
            return "skipped: a card is still waiting for a decision"
        try:
            result = telegram_instagram_service.finalize_next_and_notify(kind=slot.kind)
        except TelegramInstagramError as exc:
            return f"nothing sent: {exc}"
        return f"sent candidate {result.candidate_id}"

    async def _run(self) -> None:
        while True:
            try:
                now = datetime.now(_timezone())
                slot = self.due(now)
                if slot is not None:
                    outcome = await asyncio.to_thread(self.fire, slot, now)
                    log.info("posting slot %02d:%02d (%s): %s", slot.hour, slot.minute, slot.kind, outcome)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 -- a bad tick must not end the schedule
                log.warning("posting schedule tick failed: %s", exc)
            await asyncio.sleep(_TICK_SECONDS)

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())
        log.info("posting schedule started: %s", ", ".join(
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
