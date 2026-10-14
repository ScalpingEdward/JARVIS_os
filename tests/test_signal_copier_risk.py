from datetime import datetime, timezone

from signal_copier.risk import AccountState, breached, day_start, may_open
from signal_copier.sizing import RiskProfile

P = RiskProfile()  # 4 % daily, 8 % overall


def state(balance=10_000, equity=None, day_start_balance=10_000, open_=()):
    return AccountState(10_000, day_start_balance, balance, balance if equity is None else equity, tuple(open_))


def test_fresh_day_allows_a_half_percent_trade():
    assert may_open(state(), P, -50).ok


def test_seven_open_losers_plus_one_more_still_fits_but_eight_does_not():
    assert may_open(state(open_=[-50] * 7), P, -50).ok        # 400 = exactly 4 %
    assert not may_open(state(open_=[-50] * 8), P, -50).ok


def test_realised_losses_today_count():
    v = may_open(state(balance=9_650), P, -50)                # -350 booked + -50 = -400
    assert v.ok
    v = may_open(state(balance=9_640), P, -50)
    assert not v.ok and "daily" in v.reason


def test_breakeven_positions_cost_nothing_and_locked_profit_is_not_spent():
    assert may_open(state(balance=9_650, open_=[0.0, 0.0, 120.0]), P, -50).ok
    assert not may_open(state(balance=9_640, open_=[120.0]), P, -50).ok


def test_position_without_sl_blocks_everything():
    v = may_open(state(open_=[None]), P, -50)
    assert not v.ok and "no stop loss" in v.reason


def test_overall_stop_after_bad_days():
    # Day started at 9 250 (-7.5 %): daily room is 400, overall room only 50.
    assert may_open(state(balance=9_250, day_start_balance=9_250), P, -50).ok
    v = may_open(state(balance=9_250, day_start_balance=9_250), P, -60)
    assert not v.ok and "overall" in v.reason


def test_daily_floor_uses_initial_balance_not_current():
    # After a winning week the day starts at 11 000; 4 % of the INITIAL 10 000 = 400.
    s = state(balance=11_000, day_start_balance=11_000, equity=10_601)
    assert not breached(s, P).ok
    assert breached(state(balance=11_000, day_start_balance=11_000, equity=10_600), P).ok


def test_breach_on_floating_loss():
    assert breached(state(equity=9_600), P).ok
    assert not breached(state(equity=9_601), P).ok


def test_day_starts_at_prague_midnight_summer_and_winter():
    summer = datetime(2026, 7, 1, 22, 30, tzinfo=timezone.utc)   # 00:30 in Prague, next day
    assert day_start(summer).isoformat() == "2026-07-02T00:00:00+02:00"
    winter = datetime(2026, 1, 15, 22, 30, tzinfo=timezone.utc)  # 23:30 in Prague, same day
    assert day_start(winter).isoformat() == "2026-01-15T00:00:00+01:00"
