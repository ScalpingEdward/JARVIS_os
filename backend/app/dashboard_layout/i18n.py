"""The dashboard in AURON's language (Brano, 2026-10-23: "the language changes, the dashboard and menus do not").

The dashboard is written in German. Each German text it shows -- with its numbers taken out ("+# weitere") --
is translated once per language by a small model and kept in the database; every screen then takes it from
there. 32 languages would be thousands of hand-made lines; this way a new label translates itself the first
time it is seen in that language. The user's own data (mails, notes, names, chat) is never sent here -- the
dashboard leaves it out.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

import httpx

from app.db import SessionLocal
from app.db_models import AppSettingRow

MAX_TEXT = 300
BATCH = 120


class I18nError(ValueError):
    pass


def _key(lang: str) -> str:
    return f"i18n.{lang}"


def table(lang: str) -> dict[str, str]:
    try:
        with SessionLocal() as s:
            row = s.get(AppSettingRow, _key(lang))
        return json.loads(row.value) if row else {}
    except Exception:  # noqa: BLE001 -- no database: the dashboard stays German
        return {}


def _store(lang: str, t: dict[str, str]) -> None:
    with SessionLocal() as s:
        row = s.get(AppSettingRow, _key(lang)) or AppSettingRow(key=_key(lang))
        row.value = json.dumps(t, ensure_ascii=False)
        row.updated_at = datetime.now(timezone.utc)
        s.merge(row)
        s.commit()


def _ask(texts: list[str], language: str, client: httpx.Client | None = None) -> dict[str, str]:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise I18nError("ANTHROPIC_API_KEY is not set")
    prompt = (f"Translate these German user-interface texts of a trading and personal-assistant dashboard into "
              f"{language}. Short and natural like an app's interface, not literal. Keep '#' exactly where it is "
              f"(a number goes there), keep symbols, arrows, emoji, currency codes, brand names (AURON, Instagram, "
              f"Telegram, MT5, Smart Money, Spotify) and trading terms traders use in English (SL, TP, Buy, Sell, "
              f"Lots, EMA, Fib) unchanged. Answer with JSON only: an object mapping each German text to its "
              f"translation.\n\n" + json.dumps(texts, ensure_ascii=False))
    c = client or httpx.Client()
    try:
        r = c.post("https://api.anthropic.com/v1/messages", timeout=90, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": os.getenv("AURON_I18N_MODEL") or "claude-haiku-5-5", "max_tokens": 8000,
                  "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", []))
    finally:
        if client is None:
            c.close()
    m = re.search(r"\{.*\}", text, re.S)
    out = json.loads(m.group(0)) if m else {}
    # a translation that lost or gained a number slot would put the numbers in the wrong place: dropped
    return {k: str(v) for k, v in out.items() if k in texts and str(v).count("#") == k.count("#")}


def translate(lang: str, texts: list[str], language_name: str, client: httpx.Client | None = None) -> dict[str, str]:
    """The table for these texts; the ones not yet known are translated now and kept."""
    if lang == "de":
        return {}
    texts = list(dict.fromkeys(t for t in texts if t and len(t) <= MAX_TEXT))
    t = table(lang)
    missing = [x for x in texts if x not in t]
    for i in range(0, len(missing), BATCH):
        t.update(_ask(missing[i:i + BATCH], language_name, client))
        _store(lang, t)
    return {x: t[x] for x in texts if x in t}
