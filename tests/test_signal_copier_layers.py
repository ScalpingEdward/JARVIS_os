"""Layering, against the fake terminal and against the group's real wording."""
from types import SimpleNamespace

import pytest

from signal_copier.book import Book
from signal_copier.copier import Copier
from signal_copier.layers import Event, classify, layer_to_close, limit_levels, trailed_sl
from signal_copier.parser import ZoneSignal, parse
from signal_copier.sizing import RiskProfile
from test_signal_copier_copier import CHAT, FakeTerminal

SELL = """1. GOLD SELL SETUP

Gold Sell Zone 4192 - 4198

SL : 4203

TP1 : 4187
TP2 : 4182
TP3 : 4177
TP4 : Hold

🥷 Use our strategy with at least 5 layers of entry or more"""
CONFIG = {"strategy": "layers", "sizing": "fixed_lot", "fixed_lot": 0.01, "layers": 5, "trail_pips": 100}
LOOSE = RiskProfile(0.5, 50.0, 50.0, {"XAUUSD": 30}, 5)


def make(price=4192.0, balance=1000.0):
    t, said, now = FakeTerminal(), [], [1000.0]
    t.prices["XAUUSD.s"], t.balance = price, balance
    c = Copier(t, Book(initial_balance=balance, account=t.account), LOOSE, CONFIG, said.append, clock=lambda: now[0])
    return c, t, said, now


# --- the group's own words (from its last 600 messages) -------------------

@pytest.mark.parametrize("text, event", [
    ("TP1 HIT ✅ +100PIPS\n\n🥷 Consider closing 20% of your Entry Layers + Move stop to BreakEven", Event.PARTIAL),
    ("Trade active and running +65PIPS✅\n\n🥷 Trade is shakey consider closing 20% and moving SL to BreakEven", Event.PARTIAL),
    ("TP3 HIT ✅ +178PIPS\n\nAll Take Profit Targets SMASHED 💥 \n\nHold remaining layers and trail your SL 100 pips behind the price.", Event.TRAIL),
    ("1st entry running +330PIPS ✅\n2nd entry running +320PIPS ✅\n\nClose all now. If hold set BE. Hold rewards with Breakeven(BE)", Event.CLOSE_ALL),
    ("CUT LOSS NOW", Event.CLOSE_ALL),
    ("HIT SL", Event.SL_HIT),
    ("HTI SL", Event.SL_HIT),
    ("UPDATED", None),
    ("Hello everyone! Sorry for being a bit late with announcing the Golden Trading Cup winners!", None),
])
def test_replies_mean_what_the_group_means(text, event):
    assert classify(text) == event


def test_setup_is_a_zone_signal_with_near_and_far_end():
    assert parse(SELL) == ZoneSignal("XAUUSD", "sell", (4192.0, 4198.0), 4203.0, (4187.0, 4182.0, 4177.0), 1)
    buy = parse("2. GOLD BUY SETUP\n\nGold Buy Zone 4154 - 4147\n\nSL : 4142\n\nTP1 : 4159\nTP2 : 4164\nTP4 : Hold")
    assert buy.zone == (4154.0, 4147.0) and buy.side == "buy"


def test_zone_with_sl_inside_is_refused():
    assert "sell zone" in parse(SELL.replace("SL : 4203", "SL : 4195")).reason


# --- pure helpers ----------------------------------------------------------

def test_limits_spread_from_price_to_the_far_end_and_only_where_a_limit_can_sit():
    assert limit_levels("sell", (4192, 4198), 4192, 5) == [4193.5, 4195.0, 4196.5, 4198.0]
    assert limit_levels("sell", (4192, 4198), 4195, 4) == [4196.0, 4197.0, 4198.0]
    assert limit_levels("sell", (4192, 4198), 4190, 3) == [4195.0, 4198.0]   # below the zone: from its near end
    assert limit_levels("buy", (4154, 4147), 4154, 3) == [4150.5, 4147.0]
    assert limit_levels("sell", (4192, 4198), 4199, 5) == []                # past the far end: nothing left


def test_close_the_best_layer_but_never_the_runner():
    a, b = SimpleNamespace(profit=3.0), SimpleNamespace(profit=5.0)
    assert layer_to_close([a, b]) is b
    assert layer_to_close([a]) is None


def test_trailing_only_tightens():
    assert trailed_sl("sell", 4170.0, 4192.0, 10.0) == 4180.0
    assert trailed_sl("sell", 4185.0, 4180.0, 10.0) is None
    assert trailed_sl("buy", 4200.0, 4150.0, 10.0) == 4190.0


# --- the copier in layer mode ---------------------------------------------

def test_setup_opens_one_layer_at_market_and_four_limits_into_the_zone():
    c, t, said, _ = make()
    c.on_message(CHAT, 100, None, SELL)
    assert [p.volume for p in t.positions.values()] == [0.01]
    assert [o.price_open for o in t.orders.values()] == [4193.5, 4195.0, 4196.5, 4198.0]
    assert all(o.sl == 4203.0 for o in t.orders.values())
    assert len(c.book.get(100).legs) == 5 and "opened" in said[-1]


def test_several_setups_the_same_way_are_not_reposts():
    c, t, said, now = make()
    c.on_message(CHAT, 100, None, SELL)
    now[0] += 240
    c.on_message(CHAT, 101, None, SELL.replace("4192 - 4198", "4189 - 4194").replace("4203", "4199"))
    assert len(c.book.signals) == 2
    now[0] += 60
    c.on_message(CHAT, 102, None, SELL)  # the very same setup again
    assert "repost" in said[-1] and len(c.book.signals) == 2
    c.on_message(CHAT, 103, None, SELL.replace("1. GOLD", "3. GOLD"))  # same zone, new number (#57146/#57151)
    assert len(c.book.signals) == 3


def test_tp1_cancels_limits_closes_the_best_layer_and_moves_the_rest_to_entry():
    c, t, said, _ = make()
    c.on_message(CHAT, 100, None, SELL)
    t.fill(2)
    t.fill(3)  # the pullback filled two limits
    t.positions[1].profit, t.positions[2].profit, t.positions[3].profit = 5.0, 6.5, 8.0
    c.on_message(CHAT, 110, 100, "TP1 HIT ✅ +100PIPS\n\n🥷 Consider closing 20% of your Entry Layers + Move stop to BreakEven")
    assert not t.orders                              # unfilled limits gone
    assert sorted(t.positions) == [1, 2]             # #3 had the most profit
    assert all(p.sl == p.price_open for p in t.positions.values())


def test_partials_stop_at_the_runner_and_tp3_starts_trailing():
    c, t, said, _ = make()
    c.on_message(CHAT, 100, None, SELL)
    t.fill(2)
    partial = "TP2 HIT ✅ +101PIPS\n\n🥷 Consider closing 20% of your Entry Layers + Move stop to BreakEven"
    c.on_message(CHAT, 110, 100, partial)
    c.on_message(CHAT, 111, 100, partial)
    assert len(t.positions) == 1 and "runner" in said[-1]
    c.on_message(CHAT, 112, 100, "TP3 HIT ✅\n\nHold remaining layers and trail your SL 100 pips behind the price.")
    assert c.book.get(100).trailing
    t.prices["XAUUSD.s"] = 4170.0
    c.watch()
    (runner,) = t.positions.values()
    assert runner.sl == 4180.0                       # 100 pips = 10 $ behind


def test_close_all_and_hit_sl():
    c, t, said, _ = make()
    c.on_message(CHAT, 100, None, SELL)
    c.on_message(CHAT, 110, 100, "Close all now. If hold set BE.")
    assert not t.positions and not t.orders
    c.on_message(CHAT, 200, None, SELL.replace("4192 - 4198", "4190 - 4196").replace("4203", "4201"))
    c.on_message(CHAT, 210, 200, "HIT SL")
    assert not t.orders


def test_edited_setup_moves_sl_and_limits():
    c, t, said, now = make()
    c.on_message(CHAT, 100, None, SELL)
    now[0] += 60
    c.on_edit(CHAT, 100, SELL.replace("4192 - 4198", "4192 - 4200").replace("SL : 4203", "SL : 4205"), 1000.0)
    assert t.positions[1].sl == 4205.0
    assert [o.price_open for o in t.orders.values()] == [4194.0, 4196.0, 4198.0, 4200.0]
    assert all(o.sl == 4205.0 for o in t.orders.values())


def test_refused_setup_is_taken_when_an_edit_fixes_it():
    c, t, said, now = make(price=4185.0)  # 70 pips below the zone: too late
    c.on_message(CHAT, 100, None, SELL)
    assert not t.positions and "ran too far" in said[-1]
    now[0] += 60
    c.on_edit(CHAT, 100, SELL.replace("4192 - 4198", "4188 - 4193").replace("4203", "4198"), 1000.0)
    assert len(t.positions) == 1


def test_unfilled_limits_expire_and_loss_stop_cancels_them():
    c, t, said, now = make()
    c.on_message(CHAT, 100, None, SELL)
    now[0] += 121 * 60
    c.watch()
    assert not t.orders and "expired" in said[-1]
    c.on_message(CHAT, 200, None, SELL.replace("4192 - 4198", "4190 - 4196").replace("4203", "4201"))
    t.equity = 400.0  # through the 50 % stops
    c.watch()
    assert not t.orders and not t.positions


def test_plain_signal_profile_does_not_trade_zone_signals_and_layer_profile_ignores_plain_commands():
    t, said = FakeTerminal(), []
    plain = Copier(t, Book(initial_balance=10_000.0, account=t.account), LOOSE,
                   {"legs_without_tp": 2}, said.append, clock=lambda: 1000.0)
    plain.on_message(CHAT, 100, None, SELL)
    assert not t.positions and "layers" in said[-1]
    c, t2, said2, _ = make()
    c.on_message(CHAT, 300, None, "Close half and set breakeven")
    assert not said2
