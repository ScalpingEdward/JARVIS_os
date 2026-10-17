"""Where the last backup stands (tools/backup.py reports here) -- and a nudge when it is old.

Kept as a small JSON file in the API's /data volume: one record, no table needed.
Telegram: when a run fails or a place fails, and once a day when the last good run is
more than 48 hours old (the laptop slept through the nights, or the task is gone).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)
STATUS = Path(os.getenv("AURON_DATA_DIR", "/data")) / "backup_status.json"
STALE = timedelta(hours=48)


def _telegram(text: str) -> None:
    from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryError
    try:
        TelegramDeliveryClient().send("Backup", text)
    except TelegramDeliveryError as exc:
        log.warning("backup alert failed: %s", exc)


class BackupService:
    def __init__(self, path: Path = STATUS) -> None:
        self.path = path
        self._nagged: date | None = None

    def read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return {}

    def report(self, status: dict) -> dict:
        prev = self.read()
        rec = {"last": status, "last_ok": status if status.get("ok") else prev.get("last_ok")}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(rec), encoding="utf-8")
        bad = {k: v for k, v in (status.get("places") or {}).items() if v != "ok"}
        if not status.get("ok") or bad:
            _telegram("Backup " + ("fehlgeschlagen: " + status.get("error", "") if not status.get("ok") else "unvollständig")
                      + "".join(f"\n• {k}: {v}" for k, v in bad.items()))
        return self.view()

    def view(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        rec = self.read()
        ok = rec.get("last_ok")
        age = (now - datetime.fromisoformat(ok["at"])).total_seconds() / 3600 if ok else None
        return {"last": rec.get("last"), "last_ok_at": ok["at"] if ok else None, "age_hours": round(age, 1) if age is not None else None,
                "stale": age is None or age > STALE.total_seconds() / 3600}

    def check(self, now: datetime | None = None) -> bool:
        v = self.view(now)
        today = (now or datetime.now(timezone.utc)).date()
        if v["stale"] and self._nagged != today:
            self._nagged = today
            _telegram("Seit über 48 Stunden kein erfolgreiches Backup, Sir. Lief der Laptop nachts? "
                      "Von Hand: python tools/backup.py")
            return True
        return False


class BackupWatch:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def _run(self) -> None:
        await asyncio.sleep(600)  # let a fresh start settle; the nightly run may be on its way
        while True:
            try:
                backup_service.check()
            except Exception as exc:  # noqa: BLE001
                log.warning("backup check: %s", exc)
            await asyncio.sleep(3600)

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


backup_service = BackupService()
backup_watch = BackupWatch()
