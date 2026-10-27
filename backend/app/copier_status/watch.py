"""A copier that stops reporting is a copier that stops copying -- say so on Telegram.

On 2026-10-17 both copiers and the market feed were gone for 40 minutes and only the
red dots on the dashboard knew. Now: once a copier has sent nothing for 5 minutes, Telegram
and the AURON app say so (the 'copier' route of app/push), once; and again when it is back.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .models import CopierState
from .service import copier_status_service

log = logging.getLogger(__name__)

# "a few minutes" (Brano, 2026-10-27) -- not the dashboard's 10-minute 'offline': on 2026-10-27 both copiers
# were gone for an hour while three positions were open. A copier pushes every few seconds, so 5 minutes of
# nothing is not a hiccup.
DOWN_AFTER = timedelta(minutes=5)


def _telegram(text: str) -> None:
    from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryError
    try:
        TelegramDeliveryClient().send("Kopierer", text)
    except TelegramDeliveryError as exc:
        log.warning("copier alert failed: %s", exc)


class CopierWatch:
    def __init__(self) -> None:
        self.down: set[str] = set()
        self._task: asyncio.Task | None = None

    def check(self) -> list[str]:
        said = []
        now = datetime.now(timezone.utc)
        for a in copier_status_service.list():
            name = a.label or a.profile
            if now - a.received_at >= DOWN_AFTER and a.profile not in self.down:
                self.down.add(a.profile)
                since = a.received_at.astimezone(ZoneInfo("Europe/Berlin"))
                said.append(f"⚠ {name} ist offline -- seit {since:%H:%M} keine Meldung. Kopiert nicht! "
                            "Laptop wach? MT5 offen? Neu starten: Verknüpfung 'Copier …' im Autostart-Ordner.")
            elif a.state == CopierState.live and a.profile in self.down:
                self.down.discard(a.profile)
                said.append(f"✅ {name} läuft wieder.")
        for text in said:
            _telegram(text)
        return said

    async def _run(self) -> None:
        # a fresh API start knows nothing yet: what is offline now counts as already reported
        now = datetime.now(timezone.utc)
        self.down = {a.profile for a in copier_status_service.list() if now - a.received_at >= DOWN_AFTER}
        while True:
            await asyncio.sleep(60)
            try:
                await asyncio.to_thread(self.check)
            except Exception as exc:  # noqa: BLE001
                log.warning("copier watch: %s", exc)

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


copier_watch = CopierWatch()
