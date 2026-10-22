"""Which Telegram messages Brano gets -- switched by word to AURON ("keine Telegram-Nachrichten mehr",
"nur noch Trades", "Mails wieder an").

Categories:
  mail      important mail, Gmail sign-in expired
  markets   insider buys, macro dates
  watchlist price alerts of the watchlist (e.g. Verizon down 5 %)
  instagram the posting schedule's reminders ("die letzte Karte wartet noch", "verpasst"); the approval
            card itself and the answers to his taps are not affected
  copier    a copier offline / back, results of commands
  trades    every trade report of the copier bot (opened, BE, SL to TP1, closed)
  system    backups
  other     everything else

What always gets through, muted or not: cards with buttons (an approval waiting for him -- Instagram,
a mail draft, "close all") and a copier's real trouble (errors, failed orders, trading stopped).
Muting is for noise, never for something he has to act on.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from app.db import SessionLocal
from app.db_models import AppSettingRow

KEY = "telegram.mute"
CATEGORIES = ("mail", "markets", "watchlist", "instagram", "copier", "trades", "system", "other")
TITLES = {
    "Wichtige Post": "mail", "Mail": "mail", "Gmail": "mail",
    "Beobachteter Insider": "markets", "Insider-Kauf": "markets", "Mehrere Insider kaufen": "markets",
    "Makro in 30 Minuten": "markets",
    "Watchlist": "watchlist", "Instagram-Zeitplan": "instagram", "Kopierer": "copier", "Backup": "system",
}
# a copier's message that is trouble, not news: it always gets through
TROUBLE = re.compile(r"ERROR|FAILED|FEHLER|STOPPED|ABGEBROCHEN|not traded|loss stop|could not", re.I)


class MuteError(ValueError):
    pass


def muted() -> dict[str, bool]:
    try:
        with SessionLocal() as s:
            row = s.get(AppSettingRow, KEY)
        stored = json.loads(row.value) if row else {}
    except Exception:  # noqa: BLE001 -- no database: nothing is muted rather than everything
        stored = {}
    return {c: bool(stored.get(c, False)) for c in CATEGORIES}


def set_muted(category: str, mute: bool) -> dict[str, bool]:
    """category: one of CATEGORIES, or "all"."""
    cur = muted()
    if category == "all":
        cur = {c: mute for c in CATEGORIES}
    elif category in CATEGORIES:
        cur[category] = mute
    else:
        raise MuteError(f"category must be one of {CATEGORIES} or 'all'")
    with SessionLocal() as s:
        s.merge(AppSettingRow(key=KEY, value=json.dumps(cur), updated_at=datetime.now(timezone.utc)))
        s.commit()
    return cur


def category_of(title: str) -> str:
    return next((c for t, c in TITLES.items() if (title or "").startswith(t)), "other")


def allows(title: str) -> bool:
    return not muted()[category_of(title)]


def trades_quiet() -> bool:
    return muted()["trades"]
