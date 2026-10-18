"""The account's voice for captions: character, style, themes -- written once in the dashboard.

Until someone writes their own, the built-in DEFAULT_BRAND_VOICE (Brano's) is the voice. That is
the product's starting text, not a stand-in for a failure: a database error raises.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.db import SessionLocal
from app.db_models import AppSettingRow

KEY = "instagram.voice"
MAX_LEN = 6000


def current() -> str:
    from .caption_writer import DEFAULT_BRAND_VOICE
    with SessionLocal() as s:
        row = s.get(AppSettingRow, KEY)
    return row.value if row and row.value.strip() else DEFAULT_BRAND_VOICE


def is_default() -> bool:
    with SessionLocal() as s:
        row = s.get(AppSettingRow, KEY)
    return not (row and row.value.strip())


def save(text: str) -> None:
    """An empty text goes back to the built-in voice."""
    text = text.strip()[:MAX_LEN]
    with SessionLocal() as s:
        row = s.get(AppSettingRow, KEY)
        if not text:
            if row:
                s.delete(row)
        else:
            s.merge(AppSettingRow(key=KEY, value=text, updated_at=datetime.now(timezone.utc)))
        s.commit()
