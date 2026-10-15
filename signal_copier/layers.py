"""Layering: several small entries across a zone, closed piece by piece, a runner at the end.

How "VIP SIGNALS Inner Circle" trades, read off 600 of its messages
(2026-09-30 to 10-15):

    GOLD SELL SETUP  Zone 4192 - 4198  SL 4203  TP1..TP3, TP4 Hold
    "Trade active and running ... shakey, consider closing 20% and BE"
    "TP1 HIT / TP2 HIT ... consider closing 20% of your Entry Layers + BE"
    "TP3 HIT ... All Take Profit Targets SMASHED ... trail your SL 100 pips"
    "Close all now. If hold set BE."   /   "HIT SL"
    The setup itself is often edited a minute later ("UPDATED").

What the copier does with it:

    open    layer 1 at market, layers 2..n as limit orders spread from there
            to the far end of the zone (the pullback), all with the group's SL
    PARTIAL every SL to its own entry, unfilled limits cancelled, one layer
            closed -- the one in most profit; never the last one (the runner)
    TRAIL   from then on the watchdog pulls each SL to trail_pips behind price
    CLOSE   everything out
    SL_HIT  unfilled limits cancelled

Pure: no MT5, no Telegram.
"""
from __future__ import annotations

import re
from enum import StrEnum


# A setup refused at first may still be taken when an edit within this window fixes it.
EDIT_WINDOW_S = 10 * 60


class Event(StrEnum):
    PARTIAL = "partial"    # close 20 % + breakeven
    TRAIL = "trail"        # all TPs done, trail the rest
    CLOSE_ALL = "close_all"
    SL_HIT = "sl_hit"


def classify(text: str) -> Event | None:
    """A reply in a layering group -> what it asks for. None: commentary."""
    low = text.lower()
    if re.search(r"\bclose\s+all\b|\bcut\s+(the\s+)?loss", low):  # "CUT LOSS NOW" (#57244)
        return Event.CLOSE_ALL
    if re.search(r"\b(hit|hti)\s+sl\b|\bsl\s+hit\b|\bstopped\s+out\b", low):  # "HTI SL" (#57112)
        return Event.SL_HIT
    if re.search(r"\btrail", low):
        return Event.TRAIL
    if re.search(r"\bclos\w*\s+\d+\s*%|\bbreak\s*-?even\b|\bmove\s+(stop|sl)\s+to\s+be\b", low):
        return Event.PARTIAL
    return None


def limit_levels(side: str, zone: tuple[float, float], price: float, layers: int, digits: int = 2) -> list[float]:
    """Prices for layers 2..n: evenly from where price is (or the zone's near end) to its far end.

    Only levels a limit order can take: above price for a sell, below for a buy.
    """
    near, far = zone
    if layers < 2:
        return []
    inside = (near <= price <= far) if side == "sell" else (far <= price <= near)
    start = price if inside else near
    step = (far - start) / (layers - 1)
    levels = [round(start + step * i, digits) for i in range(1, layers)]
    return [lv for lv in levels if (lv > price if side == "sell" else lv < price)]


def layer_to_close(positions: list) -> object | None:
    """The open layer in most profit -- but never the last one: that is the runner."""
    if len(positions) < 2:
        return None
    return max(positions, key=lambda p: p.profit)


def trailed_sl(side: str, price: float, current_sl: float, distance: float) -> float | None:
    """The new SL trail_pips behind price, or None when that would not tighten it."""
    if side == "buy":
        new = price - distance
        return new if new > current_sl + 1e-9 else None
    new = price + distance
    return new if current_sl == 0 or new < current_sl - 1e-9 else None
