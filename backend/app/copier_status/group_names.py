"""Display names for signal groups -- "VIP SIGNALS Ninja Inner Circle" shown as "NINJA".

The copier keeps reporting the group under its Telegram title (that is how it finds the chat and
how its trades are tagged); only what the dashboard, the announcements and AURON show changes.
Renaming is reversible: an empty name brings the original back.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.db import SessionLocal
from app.db_models import AppSettingRow

KEY = "copier.group_names"
MAX_LEN = 60


class GroupNameError(ValueError):
    pass


def names() -> dict[str, str]:
    """original -> display"""
    with SessionLocal() as s:
        row = s.get(AppSettingRow, KEY)
    try:
        return json.loads(row.value) if row else {}
    except ValueError:
        return {}


def _store(m: dict[str, str]) -> None:
    with SessionLocal() as s:
        if m:
            s.merge(AppSettingRow(key=KEY, value=json.dumps(m, ensure_ascii=False), updated_at=datetime.now(timezone.utc)))
        elif (row := s.get(AppSettingRow, KEY)) is not None:
            s.delete(row)
        s.commit()


def rename(group: str, new: str, known: list[str]) -> dict:
    """group: the original or the current name, or a unique part of either (case does not matter).
    known: the originals the copiers report right now."""
    m = names()
    q = (group or "").strip().lower()
    if not q:
        raise GroupNameError("which group?")
    cands = sorted(set(known) | set(m))
    exact = [o for o in cands if q in (o.lower(), m.get(o, "").lower())]
    hits = exact or [o for o in cands if q in o.lower() or q in m.get(o, "").lower()]
    if not hits:
        raise GroupNameError(f"no group matches {group!r}; groups: {[m.get(o, o) for o in cands]}")
    if len(hits) > 1:
        raise GroupNameError(f"{group!r} matches several groups: {[m.get(o, o) for o in hits]} -- be more precise")
    original, new = hits[0], (new or "").strip()[:MAX_LEN]
    if new and new != original:
        m[original] = new
    else:
        m.pop(original, None)
    _store(m)
    return {"original": original, "shown_as": m.get(original, original)}


def apply(status, m: dict[str, str] | None = None):
    """The status with display names in its groups, positions, closed trades and timings."""
    m = names() if m is None else m
    if not m:
        return status
    for g in status.groups:
        g.name = m.get(g.name, g.name)
    for p in (*status.open_positions, *status.closed):
        p.group = m.get(p.group, p.group)
    for t in status.timings:
        if isinstance(t.get("group"), str):
            t["group"] = m.get(t["group"], t["group"])
    return status


def originals(statuses) -> list[str]:
    """Group names as the copiers report them (statuses without apply())."""
    return sorted({g.name for s in statuses for g in s.groups})
