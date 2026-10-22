"""Which cards the dashboard shows, where, and in what order -- plus the notes card.

Kept in the database (app_settings), not the browser: the layout is the same on every screen, and
AURON can change it on Brano's word. Built-in cards have fixed ids; added cards get an id of their
own and a type from CATALOG.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.db import SessionLocal
from app.db_models import AppSettingRow

LAYOUT_KEY = "dashboard.layout"
NOTES_KEY = "dashboard.notes"

BUILTIN = {"trading": "Trading", "watch": "Watchlist", "insta": "Instagram", "mail": "Post", "smart": "Smart Money"}
# added cards: type -> (name, what it needs)
CATALOG = {
    "price": ("Kurs", "ein Wert aus der Watchlist, z. B. Gold"),
    "copier": ("Kopierer & Bots", "Status je Konto, Pause/Weiter"),
    "notes": ("Notizen", "To-do, von Hand oder von AURON"),
    # Brano, 2026-10-22
    "clock": ("Marktuhr", "welche Session läuft, ICT-Killzones mit Countdown"),
    "positions": ("Offene Trades", "alle Positionen live, ein Klick öffnet den Chart"),
    "performance": ("Performance", "Equity-Kurve und Gewinn pro Tag, Woche, Monat je Gruppe"),
}
DEFAULT = {"left": ["trading", "watch"], "right": ["insta", "mail", "smart"], "hidden": [], "custom": {}}
MAX_CARDS = 14


class LayoutError(ValueError):
    pass


def _read(key: str):
    with SessionLocal() as s:
        row = s.get(AppSettingRow, key)
    return (json.loads(row.value), row.updated_at) if row else (None, None)


def _write(key: str, value) -> None:
    with SessionLocal() as s:
        s.merge(AppSettingRow(key=key, value=json.dumps(value, ensure_ascii=False), updated_at=datetime.now(timezone.utc)))
        s.commit()


def _label(card_id: str, custom: dict) -> str:
    if card_id in BUILTIN:
        return BUILTIN[card_id]
    c = custom.get(card_id, {})
    name = CATALOG.get(c.get("type"), ("?",))[0]
    return f"{name}: {c['config']['name']}" if c.get("type") == "price" else name


def get() -> dict:
    layout, at = _read(LAYOUT_KEY)
    layout = layout or json.loads(json.dumps(DEFAULT))
    # a built-in card that is nowhere (a newer version added it) shows up on the right
    placed = set(layout["left"]) | set(layout["right"]) | set(layout["hidden"])
    layout["right"] += [c for c in BUILTIN if c not in placed]
    return {**layout, "updated_at": at.isoformat() if at else None,
            "labels": {c: _label(c, layout["custom"]) for c in layout["left"] + layout["right"] + layout["hidden"]},
            "catalog": {k: {"name": n, "needs": d} for k, (n, d) in CATALOG.items()}}


def save(layout: dict) -> dict:
    """Check and store a whole layout (the dashboard editor sends it this way)."""
    left, right, hidden = (list(layout.get(k) or []) for k in ("left", "right", "hidden"))
    custom = dict(layout.get("custom") or {})
    ids = left + right + hidden
    if len(ids) != len(set(ids)):
        raise LayoutError("a card is placed twice")
    if len(ids) > MAX_CARDS:
        raise LayoutError(f"at most {MAX_CARDS} cards")
    for c in ids:
        if c not in BUILTIN and c not in custom:
            raise LayoutError(f"unknown card {c!r}")
    for cid, c in custom.items():
        if c.get("type") not in CATALOG:
            raise LayoutError(f"unknown card type {c.get('type')!r}")
        if c["type"] == "price" and not str((c.get("config") or {}).get("name", "")).strip():
            raise LayoutError("a price card needs a watchlist name")
    custom = {cid: c for cid, c in custom.items() if cid in ids}   # removed cards go for good
    missing = [c for c in BUILTIN if c not in ids]
    _write(LAYOUT_KEY, {"left": left, "right": right, "hidden": hidden + missing, "custom": custom})
    return get()


# ---- single steps, for AURON ------------------------------------------------------------
def _find(layout: dict, card: str) -> str:
    """A card by id, built-in name or label ("Gold", "Instagram", "Notizen")."""
    q = card.strip().lower()
    for cid, label in layout["labels"].items():
        if q in (cid.lower(), label.lower()) or (":" in label and q == label.split(":", 1)[1].strip().lower()):
            return cid
    raise LayoutError(f"no card {card!r} -- there are: {', '.join(layout['labels'].values())}")


def _strip(layout: dict) -> dict:
    return {k: layout[k] for k in ("left", "right", "hidden", "custom")}


def place(card: str, side: str, position: int | None = None) -> dict:
    """Show a card on 'left' or 'right' (position 1 = top), or 'hidden' to hide it."""
    if side not in ("left", "right", "hidden"):
        raise LayoutError("side is left, right or hidden")
    layout = get()
    cid = _find(layout, card)
    lay = _strip(layout)
    for k in ("left", "right", "hidden"):
        if cid in lay[k]:
            lay[k].remove(cid)
    at = len(lay[side]) if position is None else max(0, min(position - 1, len(lay[side])))
    lay[side].insert(at, cid)
    return save(lay)


def add(card_type: str, side: str = "right", name: str | None = None) -> dict:
    if card_type not in CATALOG:
        raise LayoutError(f"card types: {', '.join(CATALOG)}")
    if side not in ("left", "right"):
        raise LayoutError("side is left or right")
    lay = _strip(get())
    cid = f"{card_type}-{uuid.uuid4().hex[:6]}"
    lay["custom"][cid] = {"type": card_type, "config": {"name": name.strip()} if name else {}}
    lay[side].insert(0, cid)
    return save(lay)


def remove(card: str) -> dict:
    """Added cards go; built-in ones are only hidden."""
    layout = get()
    cid = _find(layout, card)
    if cid in BUILTIN:
        return place(cid, "hidden")
    lay = _strip(layout)
    for k in ("left", "right", "hidden"):
        if cid in lay[k]:
            lay[k].remove(cid)
    return save(lay)


def reset() -> dict:
    return save(json.loads(json.dumps(DEFAULT)))


# ---- notes ----------------------------------------------------------------------------
def notes() -> list[dict]:
    return _read(NOTES_KEY)[0] or []


def add_note(text: str, by: str = "brano") -> list[dict]:
    text = text.strip()[:300]
    if not text:
        raise LayoutError("empty note")
    items = notes()
    items.insert(0, {"id": uuid.uuid4().hex[:8], "text": text, "done": False, "by": by, "at": datetime.now(timezone.utc).isoformat()})
    _write(NOTES_KEY, items[:100])
    return items


def set_note(note_id: str, done: bool | None = None, delete: bool = False) -> list[dict]:
    items = notes()
    if not any(n["id"] == note_id for n in items):
        raise LayoutError("no such note")
    items = [n for n in items if not (delete and n["id"] == note_id)]
    for n in items:
        if n["id"] == note_id and done is not None:
            n["done"] = done
    _write(NOTES_KEY, items)
    return items
