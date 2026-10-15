"""Lot size from risk, and the check whether price has run away from the signal.

Pure arithmetic: the broker values (tick size, tick value, volume steps) are
passed in, so this runs without MT5. Next to MT5 they come from symbol_info().
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RiskProfile:
    """One per account -- a challenge and a live account want different numbers."""
    risk_per_position_pct: float = 0.5
    # Stops trading before the prop firm's limit is touched, not at it.
    daily_loss_stop_pct: float = 4.0
    overall_loss_stop_pct: float = 8.0
    # How far price may be from the signal's entry, in pips per symbol.
    max_entry_deviation_pips: dict[str, float] = field(default_factory=dict)
    default_entry_deviation_pips: float = 3.0


@dataclass(frozen=True)
class SymbolSpec:
    tick_size: float
    tick_value: float  # account currency per tick per 1.0 lot
    volume_min: float
    volume_max: float
    volume_step: float


def pip_size(symbol: str) -> float:
    if symbol == "XAUUSD":
        return 0.1
    if symbol == "XAGUSD":
        return 0.01
    if symbol in {"NAS100", "US30", "US500", "GER40", "BTCUSD"}:
        return 1.0
    if symbol == "USOIL":
        return 0.01
    return 0.01 if symbol.endswith("JPY") else 0.0001


def lots_for_risk(balance: float, risk_pct: float, entry: float, sl: float, spec: SymbolSpec) -> float:
    """Largest lot size whose loss at SL stays within risk_pct of balance.

    Rounds down, never up: 0 means even volume_min would risk too much, and
    the caller must skip the trade rather than open it bigger than allowed.
    """
    distance = abs(entry - sl)
    if distance <= 0:
        raise ValueError("entry and sl are equal")
    loss_per_lot = distance / spec.tick_size * spec.tick_value
    raw = balance * risk_pct / 100 / loss_per_lot
    steps = math.floor(raw / spec.volume_step + 1e-9)
    lots = round(steps * spec.volume_step, 8)
    if lots < spec.volume_min:
        return 0.0
    return min(lots, spec.volume_max)


def fixed_lots(lot: float, spec: SymbolSpec) -> float:
    """A set lot size per position, fitted to the broker's step. 0: below its minimum -- skip.

    For layering groups (several 0.01 entries, partial closes, a runner):
    their management only works if every position has the size they assume.
    """
    steps = math.floor(lot / spec.volume_step + 1e-9)
    lots = round(steps * spec.volume_step, 8)
    if lots < spec.volume_min:
        return 0.0
    return min(lots, spec.volume_max)


def entry_deviation_ok(symbol: str, side: str, signal_entry: float, price: float, profile: RiskProfile) -> bool:
    """Too late if price ran further than allowed in the trade's direction.

    A better price than the signal (buy below, sell above) is always fine --
    it only shortens the distance to TP and lengthens the one to SL, and the
    lot size is computed from the real price anyway.
    """
    limit = profile.max_entry_deviation_pips.get(symbol, profile.default_entry_deviation_pips)
    against = (price - signal_entry) if side == "buy" else (signal_entry - price)
    return against / pip_size(symbol) <= limit + 1e-9
