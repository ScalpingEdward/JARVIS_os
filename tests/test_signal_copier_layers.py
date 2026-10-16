"""Layering as Brano trades it: one setup = one layer = four positions, TP1-TP3 and a runner."""
import pytest

from signal_copier.book import Book
from signal_copier.copier import Copier
from signal_copier.layers import Event, Kind, classify, trailed_sl
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
CONFIG = {"strategy": "layers", "sizing": "fixed_lot", "fixed_lot": 0.01, "trail_pips": 100}
LOOSE = RiskProfile(0.5, 50.0, 50.0, {"XAUUSD": 30}, 5)
TP1 = "TP1 HIT ✅ +100PIPS\n\n🥷 Consider closing 20% of your Entry Layers + Move stop to BreakEven"
TP2 = "TP2 HIT ✅ +101PIPS\n\n🥷 Consider closing 20% of your Entry Layers + Move stop to BreakEven"
TP3 = "TP3 HIT ✅ +178PIPS\n\nAll Take Profit Targets SMASHED 💥 \n\nHold remaining layers and trail your SL 100 pips behind the price."
SHAKY = "Trade active and running +65PIPS✅\n\n🥷 Trade is shakey consider closing 20% and moving SL to BreakEven"


def make(price=4192.0, balance=1000.0):
    t, said, now = FakeTerminal(), [], [1000.0]
    t.prices["XAUUSD.s"], t.balance = price, balance
    c = Copier(t, Book(initial_balance=balance, account=t.account), LOOSE, CONFIG, said.append, clock=lambda: now[0])
    return c, t, said, now


def layer(c, t, msg_id=100):
    """Position number -> position, of one setup."""
    return {int(n): t.positions[tk] for n, tk in c.book.get(msg_id).legs.items() if tk in t.positions}


# --- the group's own words (from its last 600 messages) -------------------

@pytest.mark.parametrize("text, event", [
    (SHAKY, Event(Kind.SHAKY)),
    (TP1, Event(Kind.TP_HIT, 1)),
    (TP2, Event(Kind.TP_HIT, 2)),
    (TP3, Event(Kind.TRAIL, 3)),
    ("1st entry running +330PIPS ✅\n2nd entry running +320PIPS ✅\n\nClose all now. If hold set BE.", Event(Kind.CLOSE_ALL)),
    ("CUT LOSS NOW", Event(Kind.CLOSE_ALL)),
    ("HIT SL", Event(Kind.SL_HIT)),
    ("HTI SL", Event(Kind.SL_HIT)),
    ("UPDATED", None),
    ("Hello everyone! Sorry for being a bit late with announcing the Golden Trading Cup winners!", None),
    ("London performance of our VIP Inner Circle Group\n\n1- GOLD BUY 60 PIPS ✅\n2- GOLD BUY HIT SL\n3- GOLD BUY Cut Loss", None),
    ("London weekly performance of our VIP Inner Circle Group\n\nMonday\n1- GOLD SELL HIT SL\n16- GOLD BUY Cut Loss", None),
])
def test_messages_mean_what_the_group_means(text, event):
    assert classify(text) == event


def test_setup_is_a_zone_signal_with_its_number():
    assert parse(SELL) == ZoneSignal("XAUUSD", "sell", (4192.0, 4198.0), 4203.0, (4187.0, 4182.0, 4177.0), 1)
    buy = parse("2. GOLD BUY SETUP\n\nGold Buy Zone 4154 - 4147\n\nSL : 4142\n\nTP1 : 4159\nTP2 : 4164\nTP4 : Hold")
    assert buy.zone == (4154.0, 4147.0) and buy.side == "buy" and buy.number == 2


def test_zone_with_sl_inside_is_refused():
    assert "sell zone" in parse(SELL.replace("SL : 4203", "SL : 4195")).reason


def test_trailing_only_tightens():
    assert trailed_sl("sell", 4170.0, 4192.0, 10.0) == 4180.0
    assert trailed_sl("sell", 4185.0, 4180.0, 10.0) is None
    assert trailed_sl("buy", 4200.0, 4150.0, 10.0) == 4190.0


# --- the copier in layer mode ---------------------------------------------

def test_setup_opens_four_positions_tp1_tp2_tp3_and_a_runner():
    c, t, said, _ = make()
    c.on_message(CHAT, 100, None, SELL)
    lay = layer(c, t)
    assert [(n, p.volume, p.sl, p.tp) for n, p in sorted(lay.items())] == [
        (1, 0.01, 4203.0, 4187.0), (2, 0.01, 4203.0, 4182.0), (3, 0.01, 4203.0, 4177.0), (4, 0.01, 4203.0, 0.0)]
    assert not t.orders and "opened" in said[-1]


def test_shaky_in_profit_closes_position_1_but_breakeven_waits_for_tp1():
    c, t, said, _ = make()
    c.on_message(CHAT, 100, None, SELL)
    for p in layer(c, t).values():
        p.profit = 2.0
    c.on_message(CHAT, 110, 100, SHAKY)
    lay = layer(c, t)
    assert sorted(lay) == [2, 3, 4] and all(p.sl == 4203.0 for p in lay.values())   # no BE yet
    t.prices["XAUUSD.s"] = 4188.0
    c.watch()
    assert all(p.sl == 4203.0 for p in lay.values())                              # TP1 4187 not reached
    t.prices["XAUUSD.s"] = 4186.9
    c.watch()
    assert all(p.sl == p.price_open for p in lay.values()) and "TP1 4187.0 reached" in said[-1]


def test_shaky_in_loss_keeps_position_1():
    # 2026-10-15/16: the group's "shaky" came while our market entry was still red;
    # position 1 was closed at a loss and the rest stopped out at entry seconds later
    c, t, said, _ = make()
    c.on_message(CHAT, 100, None, SELL)
    for p in layer(c, t).values():
        p.profit = -1.5
    c.on_message(CHAT, 110, 100, SHAKY)
    lay = layer(c, t)
    assert sorted(lay) == [1, 2, 3, 4] and all(p.sl == 4203.0 for p in lay.values()) and "kept" in said[-1]


def test_tp1_hit_only_breakeven_when_the_broker_already_closed_position_1():
    c, t, said, _ = make()
    c.on_message(CHAT, 100, None, SELL)
    del t.positions[c.book.get(100).legs["1"]]       # the broker's TP1 fired
    c.on_message(CHAT, 110, 100, TP1)
    lay = layer(c, t)
    assert sorted(lay) == [2, 3, 4] and all(p.sl == p.price_open for p in lay.values())


def test_tp_hit_closes_that_position_if_the_broker_has_not_yet():
    c, t, said, _ = make()
    c.on_message(CHAT, 100, None, SELL)
    c.on_message(CHAT, 110, 100, TP1)
    c.on_message(CHAT, 111, 100, TP2)
    assert sorted(layer(c, t)) == [3, 4]


def test_shaky_then_tp1_does_not_close_position_2():
    c, t, said, _ = make()
    c.on_message(CHAT, 100, None, SELL)
    c.on_message(CHAT, 110, 100, SHAKY)              # position 1 out
    c.on_message(CHAT, 111, 100, TP1)                # TP1 is position 1's -- already gone
    assert sorted(layer(c, t)) == [2, 3, 4]


def test_tp3_closes_position_3_and_the_runner_trails():
    c, t, said, _ = make()
    c.on_message(CHAT, 100, None, SELL)
    c.on_message(CHAT, 110, 100, TP1)
    c.on_message(CHAT, 111, 100, TP2)
    c.on_message(CHAT, 112, 100, TP3)
    lay = layer(c, t)
    assert sorted(lay) == [4] and c.book.get(100).trailing
    t.prices["XAUUSD.s"] = 4170.0
    c.watch()
    assert lay[4].sl == 4180.0                       # 100 pips = 10 $ behind


def test_the_runner_is_never_closed_by_a_partial():
    c, t, said, _ = make()
    c.on_message(CHAT, 100, None, SELL)
    for n in (1, 2, 3):
        del t.positions[c.book.get(100).legs[str(n)]]
    c.on_message(CHAT, 110, 100, SHAKY)
    assert sorted(layer(c, t)) == [4]


def test_close_all_as_reply_closes_that_setup_only_without_reply_every_setup():
    c, t, said, now = make()
    c.on_message(CHAT, 100, None, SELL)
    c.on_message(CHAT, 200, None, SELL.replace("1. GOLD", "2. GOLD").replace("4192 - 4198", "4190 - 4196").replace("4203", "4201"))
    c.on_message(CHAT, 300, 100, "Close all now. If hold set BE.")
    assert not layer(c, t, 100) and len(layer(c, t, 200)) == 4
    c.on_message(CHAT, 301, None, "Close all now")
    assert not t.positions and "every setup" in said[-1]


def test_other_instructions_without_reply_are_not_guessed():
    c, t, said, _ = make()
    c.on_message(CHAT, 100, None, SELL)
    c.on_message(CHAT, 110, None, TP1)
    assert len(t.positions) == 4


def test_a_reply_touches_only_its_own_setup():
    c, t, said, _ = make()
    c.on_message(CHAT, 100, None, SELL)
    c.on_message(CHAT, 200, None, SELL.replace("1. GOLD", "2. GOLD").replace("4192 - 4198", "4190 - 4196").replace("4203", "4201"))
    c.on_message(CHAT, 210, 200, TP1)
    assert len(layer(c, t, 100)) == 4 and all(p.sl == 4203.0 for p in layer(c, t, 100).values())
    assert sorted(layer(c, t, 200)) == [2, 3, 4]


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


def test_edited_setup_moves_sl_and_tps_but_not_a_breakeven_stop():
    c, t, said, now = make()
    c.on_message(CHAT, 100, None, SELL)
    c.on_message(CHAT, 110, 100, TP1)                # 2-4 at entry now
    c.on_message(CHAT, 200, None, SELL.replace("1. GOLD", "2. GOLD").replace("4192 - 4198", "4190 - 4196").replace("4203", "4201"))
    now[0] += 60
    edited = SELL.replace("1. GOLD", "2. GOLD").replace("4192 - 4198", "4190 - 4196").replace("SL : 4203", "SL : 4206").replace("TP2 : 4182", "TP2 : 4180")
    c.on_edit(CHAT, 200, edited, 1000.0)
    lay = layer(c, t, 200)
    assert all(p.sl == 4206.0 for p in lay.values()) and lay[2].tp == 4180.0 and lay[4].tp == 0.0
    c.on_edit(CHAT, 100, SELL.replace("SL : 4203", "SL : 4206"), 1000.0)
    assert all(p.sl == p.price_open for p in layer(c, t, 100).values())


def test_refused_setup_is_taken_when_an_edit_fixes_it():
    c, t, said, now = make(price=4187.5)  # 45 pips below the zone: too late
    c.on_message(CHAT, 100, None, SELL)
    assert not t.positions and "ran too far" in said[-1]
    now[0] += 60
    c.on_edit(CHAT, 100, SELL.replace("4192 - 4198", "4188 - 4193").replace("4203", "4198"), 1000.0)
    assert len(t.positions) == 4


def test_setup_already_past_tp1_is_not_opened():
    c, t, said, _ = make(price=4189.0)  # 30 pips from the zone: allowed, but TP1 4190 is behind it
    c.on_message(CHAT, 100, None, SELL.replace("TP1 : 4187", "TP1 : 4190").replace("TP2 : 4182", "TP2 : 4185").replace("TP3 : 4177", "TP3 : 4180"))
    assert not t.positions and "past TP1" in said[-1]


def test_loss_stop_closes_every_layer():
    c, t, said, now = make()
    c.on_message(CHAT, 100, None, SELL)
    t.equity = 400.0  # through the 50 % stops
    c.watch()
    assert not t.positions


def test_plain_signal_profile_does_not_trade_zone_signals_and_layer_profile_ignores_plain_commands():
    t, said = FakeTerminal(), []
    plain = Copier(t, Book(initial_balance=10_000.0, account=t.account), LOOSE,
                   {"legs_without_tp": 2}, said.append, clock=lambda: 1000.0)
    plain.on_message(CHAT, 100, None, SELL)
    assert not t.positions and "layers" in said[-1]
    c, t2, said2, _ = make()
    c.on_message(CHAT, 300, None, "Close half and set breakeven")
    assert not said2


def test_missed_setup_and_its_late_edit_are_not_opened():
    c, t, said, now = make()
    c.on_message(CHAT, 100, None, SELL, posted_at=now[0] - 10 * 60)
    assert not t.positions and "missed" in said[-1]
    c.on_edit(CHAT, 100, SELL.replace("SL : 4203", "SL : 4204"), now[0] - 9 * 60, now[0] - 9 * 60)
    assert not t.positions
