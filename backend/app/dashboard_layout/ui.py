"""AURON moves the dashboard on Brano's word: "öffne Trading", "zeig mir den Chart von NINJA", "mach zu".

The commands live in memory with a running number; every open dashboard asks for the ones after the last
it has seen (every 1.5 s) and carries them out. Old commands are never replayed: a dashboard that starts
takes the current number as its start.
"""
from __future__ import annotations

import itertools
import threading
import time

VIEWS = {"trading": "Trading", "watchlist": "Watchlist", "instagram": "Instagram", "smart": "Smart Money"}
_seq = itertools.count(1)
_lock = threading.Lock()
_queue: list[dict] = []
KEEP_S = 60


class UiError(ValueError):
    pass


def push(cmd: dict) -> dict:
    with _lock:
        c = {**cmd, "seq": next(_seq), "at": time.time()}
        _queue.append(c)
        del _queue[:-50]
        return c


def since(after: int) -> dict:
    now = time.time()
    with _lock:
        last = _queue[-1]["seq"] if _queue else 0
        return {"last": last, "commands": [c for c in _queue if c["seq"] > after and now - c["at"] <= KEEP_S]}


def open_view(view: str) -> dict:
    v = (view or "").lower()
    v = next((k for k, name in VIEWS.items() if v in (k, name.lower())), None)
    if not v:
        raise UiError(f"keine Ansicht {view!r}; es gibt {list(VIEWS.values())}")
    return push({"do": "open_view", "view": v})


def close_view() -> dict:
    return push({"do": "close"})


def show_chart(group: str | None = None, symbol: str | None = None) -> dict:
    """The chart of an open trade -- of a group (NINJA, ICT CRT) and/or a symbol (Gold, XAUUSD)."""
    from app.copier_status.service import copier_status_service
    o = copier_status_service.overview()
    pos = [(a.profile, p) for a in o.accounts for p in a.open_positions]
    g, s = (group or "").lower(), (symbol or "").lower().replace("gold", "xau")
    hit = [(prof, p) for prof, p in pos if (not g or g in p.group.lower()) and (not s or s in p.symbol.lower())]
    if not hit:
        raise UiError("keine offene Position" + (f" von {group}" if group else "") + (f" in {symbol}" if symbol else ""))
    prof, p = hit[0]
    push({"do": "show_chart", "ticket": p.ticket, "copier": prof})
    return {"ticket": p.ticket, "symbol": p.symbol, "group": p.group, "side": p.side, "open_positions_matching": len(hit)}
