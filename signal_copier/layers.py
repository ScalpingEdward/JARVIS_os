"""Layering: every numbered setup is one layer of four positions -- three with a TP, one runner.

How "VIP SIGNALS Inner Circle" trades, read off 600 of its messages
(2026-09-30 to 10-15), and how Brano trades it (2026-10-15):

    "3. GOLD SELL SETUP  Zone 4192 - 4198  SL 4203  TP1..TP3, TP4 Hold"
        -> one layer: positions 1-3 with TP1, TP2, TP3, position 4 the
           runner without TP; all at market, all with the group's SL
    "Trade is shakey, consider closing 20% and moving SL to BreakEven"
        -> close position 1 (the lowest TP still open), rest to entry
    "TP1 HIT / TP2 HIT ... closing 20% of your Entry Layers + BE"
        -> that TP's position is out (closed here if the broker's TP has
           not fired yet), the rest to entry
    "TP3 HIT ... trail your SL 100 pips behind the price"
        -> position 3 out, the runner trails from now on
    "Close all now" / "CUT LOSS NOW"
        -> the layer it answers; without a reply every layer of the group
    "HIT SL"  -> nothing to do, the SL did it

A reply only ever touches the layer (setup) it answers. Pure: no MT5, no Telegram.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

# A setup refused at first may still be taken when an edit within this window fixes it.
EDIT_WINDOW_S = 10 * 60


class Kind(StrEnum):
    SHAKY = "shaky"        # close the lowest TP position still open + BE
    TP_HIT = "tp_hit"      # TP n is reached: its position out + BE
    TRAIL = "trail"        # TP3 reached: position 3 out, runner trails
    CLOSE_ALL = "close_all"
    SL_HIT = "sl_hit"


@dataclass(frozen=True)
class Event:
    kind: Kind
    tp: int | None = None  # for TP_HIT / TRAIL: which TP the group says is hit

    def __str__(self) -> str:
        return f"{self.kind}{self.tp or ''}"


def classify(text: str) -> Event | None:
    """A message in a layering group -> what it asks for. None: commentary."""
    low = text.lower()
    # Session recaps list past trades ("3- GOLD BUY Cut Loss", "HIT SL") -- read as an
    # instruction, #57263 and #57357 would have closed every open setup.
    if re.search(r"\bperformance\b|\breport\b|\bleaderboard\b|\branking\b", low):
        return None
    if re.search(r"\bclose\s+all\b|\bcut\s+(the\s+)?loss", low):  # "CUT LOSS NOW" (#57244)
        return Event(Kind.CLOSE_ALL)
    if re.search(r"\b(hit|hti)\s+sl\b|\bsl\s+hit\b|\bstopped\s+out\b", low):  # "HTI SL" (#57112)
        return Event(Kind.SL_HIT)
    hit = re.search(r"\btp\s*(\d)\s*hit\b", low)
    if re.search(r"\btrail", low):
        return Event(Kind.TRAIL, int(hit.group(1)) if hit else 3)
    if hit:
        return Event(Kind.TP_HIT, int(hit.group(1)))
    if re.search(r"\bclos\w*\s+\d+\s*%|\bbreak\s*-?even\b|\bmove\s+(stop|sl)\s+to\s+be\b", low):
        return Event(Kind.SHAKY)
    return None


def trailed_sl(side: str, price: float, current_sl: float, distance: float) -> float | None:
    """The new SL trail_pips behind price, or None when that would not tighten it."""
    if side == "buy":
        new = price - distance
        return new if new > current_sl + 1e-9 else None
    new = price + distance
    return new if current_sl == 0 or new < current_sl - 1e-9 else None
