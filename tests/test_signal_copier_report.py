from datetime import datetime, timezone

from signal_copier.book import Book, TrackedSignal
from signal_copier.report import OTHER, build

GOLD_GROUP, OTHER_GROUP = -100, -200
NAMES = {GOLD_GROUP: "ICT CRT PREMIUM", OTHER_GROUP: "Second Group"}
# Wednesday 2026-10-14 10:00 UTC = 12:00 Prague; the week began Monday 12th.
NOW = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)
ACCOUNT = {"login": 700167790, "server": "PUPrime-Demo", "currency": "EUR", "balance": 10_050.0, "equity": 10_070.0}


def ts(day, hour=10):
    return datetime(2026, 10, day, hour, tzinfo=timezone.utc).timestamp()


def deal(pos, profit, day, closing=True, commission=0.0):
    return {"position_id": pos, "time": ts(day), "profit": profit, "commission": commission,
            "swap": 0.0, "fee": 0.0, "closing": closing}


def book():
    b = Book()
    b.add(TrackedSignal(1, GOLD_GROUP, "XAUUSD.s", "buy", 4151, 4141, [4170, 4200], 0, {"1": 11, "2": 12}))
    b.add(TrackedSignal(2, OTHER_GROUP, "EURUSD.s", "sell", 1.1, 1.101, [1.09], 0, {"1": 21}))
    return b


def test_profit_is_split_by_group_and_period():
    deals = [deal(11, 0, 14, closing=False, commission=-1.0), deal(11, 40.0, 14),  # today
             deal(12, -10.0, 12),   # this week
             deal(21, 25.0, 5)]     # last week
    s = build("puprime_demo", ACCOUNT, [], deals, book(), NAMES, NOW)
    gold, second = s.groups
    assert (gold.name, gold.pnl_today, gold.pnl_week, gold.pnl_total, gold.closed_trades) == \
        ("ICT CRT PREMIUM", 39.0, 29.0, 29.0, 2)
    assert (second.pnl_today, second.pnl_week, second.pnl_total) == (0, 0, 25.0)


def test_open_positions_carry_their_group_and_trades_by_hand_are_not_dropped():
    positions = [{"ticket": 12, "symbol": "XAUUSD.s", "side": "buy", "volume": 0.05,
                  "price_open": 4151, "sl": 4141, "tp": 4200, "profit": 20.0},
                 {"ticket": 99, "symbol": "GER40", "side": "sell", "volume": 1,
                  "price_open": 1, "sl": 0, "tp": 0, "profit": -5.0}]
    s = build("puprime_demo", ACCOUNT, positions, [deal(98, 7.0, 14)], book(), NAMES, NOW)
    by_name = {g.name: g for g in s.groups}
    assert by_name["ICT CRT PREMIUM"].open_pnl == 20.0 and by_name["ICT CRT PREMIUM"].open_positions == 1
    assert by_name[OTHER].open_pnl == -5.0 and by_name[OTHER].pnl_total == 7.0
    assert s.groups[-1].name == OTHER
    assert [p["group"] for p in s.open_positions] == ["ICT CRT PREMIUM", OTHER]


def test_empty_account_still_lists_its_groups_and_no_other_bucket():
    s = build("puprime_demo", ACCOUNT, [], [], Book(), NAMES, NOW)
    assert [g.name for g in s.groups] == ["ICT CRT PREMIUM", "Second Group"]
    j = s.to_json()
    assert j["account_login"] == 700167790 and j["balance"] == 10_050.0 and j["groups"][0]["pnl_total"] == 0
