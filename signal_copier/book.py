"""Which signal a message is about, and what "close half" means for it.

Pure bookkeeping, saved as JSON so a restart keeps every link between a
Telegram message and its MT5 tickets.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

# A second post of the same trade (#4251, #4146 in the channel) within this
# window completes the first one instead of opening it twice.
REPOST_WINDOW_S = 30 * 60
# TPs sent on their own belong to the latest TP-less signal this recent.
LATE_TP_WINDOW_S = 10 * 60


@dataclass
class TrackedSignal:
    msg_id: int
    chat_id: int
    symbol: str          # broker name
    side: str
    entry: float
    sl: float
    tps: list[float]
    opened_at: float
    legs: dict[str, int] = field(default_factory=dict)  # leg number -> ticket (position, or a pending order)
    # Layering only (layers.py): the zone as (near, far), the parser's symbol
    # name for pip sizes, and whether the watchdog trails the remaining SLs.
    strategy: str = "signals"
    zone: list[float] = field(default_factory=list)
    canonical: str = ""
    trailing: bool = False
    number: int | None = None  # the group's setup number, part of what makes a repost
    be_at_tp1: bool = False    # "shaky" came: move the rest to entry once price reaches TP1


@dataclass
class Book:
    signals: dict[str, TrackedSignal] = field(default_factory=dict)  # str(msg_id)
    # Every message we acted on -> the signal it concerns, so a reply to a
    # reply ("Set Breakeven" answered with "Close half") still finds it.
    about: dict[str, int] = field(default_factory=dict)
    initial_balance: float | None = None
    # "<login>@<server>" this book belongs to; everything above is about that account only.
    account: str = ""
    # Tickets whose SL should go to entry once the broker's minimum distance allows it.
    pending_be: list[int] = field(default_factory=list)
    # Set when a loss stop was hit: no new trades until halt_until (None = for good).
    halt_reason: str = ""
    halt_until: float | None = None

    def halted(self, now: float) -> bool:
        return bool(self.halt_reason) and (self.halt_until is None or now < self.halt_until)

    def add(self, s: TrackedSignal) -> None:
        self.signals[str(s.msg_id)] = s
        self.about[str(s.msg_id)] = s.msg_id

    def get(self, msg_id: int) -> TrackedSignal | None:
        return self.signals.get(str(msg_id))

    def link(self, msg_id: int, signal_id: int) -> None:
        self.about[str(msg_id)] = signal_id

    def target(self, chat_id: int, reply_to: int | None, symbol: str | None,
               open_ids: set[int]) -> tuple[TrackedSignal | None, str]:
        """The signal a command means, or None with the reason."""
        if reply_to is not None:
            sid = self.about.get(str(reply_to))
            if sid is not None:
                return self.signals[str(sid)], ""
            return None, f"reply to #{reply_to}, which is no signal I traded"
        candidates = [s for s in self.signals.values()
                      if s.chat_id == chat_id and s.msg_id in open_ids
                      and (symbol is None or s.symbol.upper().startswith(symbol))]
        if len(candidates) == 1:
            return candidates[0], ""
        if not candidates:
            return None, "no open signal matches"
        return None, f"{len(candidates)} open signals match -- not guessing"

    def repost_of(self, chat_id: int, symbol: str, side: str, now: float) -> TrackedSignal | None:
        for s in sorted(self.signals.values(), key=lambda s: -s.opened_at):
            if s.chat_id == chat_id and s.symbol == symbol and s.side == side and now - s.opened_at <= REPOST_WINDOW_S:
                return s
        return None

    def awaiting_tps(self, chat_id: int, now: float) -> TrackedSignal | None:
        for s in sorted(self.signals.values(), key=lambda s: -s.opened_at):
            if s.chat_id == chat_id and now - s.opened_at <= LATE_TP_WINDOW_S:
                return s if not s.tps else None
        return None

    def save(self, path: Path) -> None:
        data = {"signals": {k: asdict(v) for k, v in self.signals.items()},
                "about": self.about, "initial_balance": self.initial_balance,
                "account": self.account, "pending_be": self.pending_be, "halt_reason": self.halt_reason, "halt_until": self.halt_until}
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> Book:
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls({k: TrackedSignal(**v) for k, v in data["signals"].items()},
                   data["about"], data.get("initial_balance"), data.get("account", ""), data.get("pending_be", []),
                   data.get("halt_reason", ""), data.get("halt_until"))


def close_half_plan(legs: dict[str, int], open_tickets: set[int], volumes: dict[int, float],
                    volume_step: float, volume_min: float) -> tuple[list[tuple[int, float | None]], str]:
    """What "close half" closes: (ticket, volume or None for all), and why.

    Two legs: the TP1 leg IS the half. Closed already (TP1 hit, or an earlier
    "close half") means nothing more to do -- never the TP2 leg.
    One leg: half its volume, rounded down to the broker's step.
    """
    if len(legs) >= 2:
        first = legs.get("1")
        if first in open_tickets:
            return [(first, None)], "closing the TP1 leg"
        return [], "TP1 leg already closed -- half is gone, TP2 leg stays"
    if not legs:
        return [], "no legs"
    ticket = next(iter(legs.values()))
    if ticket not in open_tickets:
        return [], "position already closed"
    half = int(volumes[ticket] / 2 / volume_step + 1e-9) * volume_step
    half = round(half, 8)
    if half < volume_min:
        return [], f"half of {volumes[ticket]} is below the broker minimum {volume_min}"
    return [(ticket, half)], f"closing {half} of {volumes[ticket]}"
