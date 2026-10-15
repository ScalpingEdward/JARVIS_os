"""Daily and overall loss limits, checked before every trade and while trades run.

FTMO-style: the daily floor is the balance at midnight Prague time minus a
share of the INITIAL balance; the overall floor is the initial balance minus
a share of it. Both are set per profile, and either can be switched off
(None or 0): a prop firm needs them, an own live account may not.

The pre-trade check is worst case: every open position and the new one hit
their stop loss. Equity is not used for that -- a winner running now can
still turn around.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from signal_copier.sizing import RiskProfile

PRAGUE = ZoneInfo("Europe/Prague")


@dataclass(frozen=True)
class AccountState:
    initial_balance: float
    day_start_balance: float
    balance: float
    equity: float
    # Profit if each open position's SL is hit (negative = loss). None: no SL.
    open_pnl_at_sl: tuple[float | None, ...]


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason: str = ""


def day_start(now: datetime) -> datetime:
    """Midnight Prague time of the trading day `now` falls in."""
    local = now.astimezone(PRAGUE)
    return datetime.combine(local.date(), time(0), PRAGUE)


def floors(state: AccountState, profile: RiskProfile) -> tuple[float, float]:
    """Equity floors; a stop that is switched off (None or 0) is -inf, never reached."""
    off = float("-inf")
    daily = (state.day_start_balance - state.initial_balance * profile.daily_loss_stop_pct / 100
             if profile.daily_loss_stop_pct else off)
    overall = (state.initial_balance * (1 - profile.overall_loss_stop_pct / 100)
               if profile.overall_loss_stop_pct else off)
    return daily, overall


def may_open(state: AccountState, profile: RiskProfile, new_pnl_at_sl: float) -> Verdict:
    if any(p is None for p in state.open_pnl_at_sl):
        return Verdict(False, "an open position has no stop loss -- risk unknown")
    # A stop already beyond entry locks profit, but counting it would let the
    # next trade spend money that is not booked yet.
    worst = state.balance + sum(min(p, 0.0) for p in state.open_pnl_at_sl) + min(new_pnl_at_sl, 0.0)
    daily, overall = floors(state, profile)
    if worst < daily:
        return Verdict(False, f"daily stop: worst case {worst:.2f} below {daily:.2f}")
    if worst < overall:
        return Verdict(False, f"overall stop: worst case {worst:.2f} below {overall:.2f}")
    return Verdict(True)


def breached(state: AccountState, profile: RiskProfile) -> Verdict:
    """Equity already through a stop -- the caller closes everything."""
    daily, overall = floors(state, profile)
    if state.equity <= daily:
        return Verdict(True, f"equity {state.equity:.2f} hit daily stop {daily:.2f}")
    if state.equity <= overall:
        return Verdict(True, f"equity {state.equity:.2f} hit overall stop {overall:.2f}")
    return Verdict(False)

