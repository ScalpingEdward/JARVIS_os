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


def chart_full(on: bool | None = None) -> dict:
    """The open chart fills the window (on), goes back between the cards (off), or switches (None)."""
    return push({"do": "chart_full", "on": on})


def show_model(part_id: str) -> dict:
    """A 3D part (app/cad) in the dashboard's 3D view."""
    return push({"do": "show_model", "id": part_id})


def close_view() -> dict:
    return push({"do": "close"})


TIMEFRAMES = ("M1", "M5", "M15", "H1", "H4", "D1")
_TF_WORDS = {"1": "M1", "1m": "M1", "m1": "M1", "5": "M5", "5m": "M5", "m5": "M5", "15": "M15", "15m": "M15",
             "m15": "M15", "60": "H1", "1h": "H1", "h1": "H1", "stunde": "H1", "4h": "H4", "h4": "H4",
             "d": "D1", "d1": "D1", "1d": "D1", "tag": "D1", "daily": "D1", "tages": "D1"}


def timeframe(tf: str | None) -> str:
    """'15', '15 Minuten', 'm15', '1h', 'Stunde', '4h', 'Tag' -> M15 / H1 / H4 / D1; nothing -> M5."""
    if not tf:
        return "M5"
    t = tf.strip().lower().replace(" ", "").replace("minuten", "").replace("min", "").replace("stunden", "h")
    if t.upper() in TIMEFRAMES:
        return t.upper()
    if t in _TF_WORDS:
        return _TF_WORDS[t]
    raise UiError(f"keinen Timeframe {tf!r}; es gibt {list(TIMEFRAMES)}")


def _symbol(name: str) -> str:
    """'Gold' -> the broker's name from the watchlist (XAUUSD.s); a name not on it goes as said (the copier
    finds the broker's spelling: XAUUSD -> XAUUSD.s)."""
    from app.watchlist.service import watchlist_service
    n = name.strip().lower()
    items = [i for i in watchlist_service.get().items if i.symbol]
    hit = ([i for i in items if i.name.lower() == n or i.symbol.lower() == n]
           or [i for i in items if n in i.name.lower()])
    return hit[0].symbol if hit else name.strip().upper().replace("GOLD", "XAUUSD").replace("SILBER", "XAGUSD")


def show_chart(group: str | None = None, symbol: str | None = None, tf: str | None = None) -> dict:
    """The chart of an open trade -- of a group (NINJA, ICT CRT) and/or a symbol -- or, with no open trade
    in that symbol, the symbol's own chart from a copier's MT5 (Brano, 2026-10-22: "15 Minuten Gold")."""
    from app.copier_status.service import copier_status_service
    frame = timeframe(tf)
    o = copier_status_service.overview()
    pos = [(a.profile, p) for a in o.accounts for p in a.open_positions]
    g, s = (group or "").lower(), (symbol or "").lower().replace("gold", "xau").replace("silber", "xag")
    hit = [(prof, p) for prof, p in pos if (not g or g in p.group.lower()) and (not s or s in p.symbol.lower())]
    if hit:
        prof, p = hit[0]
        push({"do": "show_chart", "ticket": p.ticket, "copier": prof, "tf": frame})
        return {"ticket": p.ticket, "symbol": p.symbol, "group": p.group, "side": p.side, "tf": frame,
                "open_positions_matching": len(hit)}
    if group or not symbol:
        raise UiError("keine offene Position" + (f" von {group}" if group else "") + (f" in {symbol}" if symbol else ""))
    live = [a.profile for a in o.accounts if a.state == "live"] or [a.profile for a in o.accounts]
    if not live:
        raise UiError("kein Kopierer meldet sich -- ohne MT5 keine Kerzen")
    sym = _symbol(symbol)
    push({"do": "show_symbol", "symbol": sym, "copier": live[0], "tf": frame})
    return {"symbol": sym, "tf": frame, "from": live[0], "note": "Chart ohne Position; Kerzen kommen in 2-4 s"}
