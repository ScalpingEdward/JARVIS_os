from types import SimpleNamespace

from signal_copier.book import Book
from signal_copier.copier import Copier, state_path
from signal_copier.execution import Opened
from signal_copier.risk import AccountState
from signal_copier.sizing import RiskProfile, SymbolSpec

CHAT = -100
CONFIG = {"legs_without_tp": 2, "symbol_overrides": {}}
PROFILE = RiskProfile(0.5, 4.0, 8.0, {"XAUUSD": 30}, 5)


class FakeTerminal:
    """Gold at 4151, 10 000 balance; 1 lot loses 100 per 1.0 price move."""

    def __init__(self):
        self.prices = {"XAUUSD.s": 4151.0}
        self.positions = {}
        self.next_ticket = 1
        self.equity = None
        self.balance = 10_000.0
        self.too_close = False
        self.calls = []
        self.account = "1001@PUPrime-Demo"
        self.orders = {}

    def account_id(self):
        return self.account

    def tradable_symbols(self):
        return ["XAUUSD.s", "EURUSD.s"]

    def price(self, symbol, side):
        return self.prices[symbol]

    def spec(self, symbol):
        return SymbolSpec(0.01, 1.0, 0.01, 100.0, 0.01)

    def pnl_at_sl(self, symbol, side, volume, entry, sl):
        return -abs(entry - sl) * 100 * volume

    def account_state(self, initial):
        at_sl = tuple(-abs(p.price_open - p.sl) * 100 * p.volume for p in self.positions.values())
        eq = self.balance if self.equity is None else self.equity
        return AccountState(initial or 10_000.0, self.balance, self.balance, eq, at_sl)

    def open_position(self, symbol, side, volume, sl, tp, signal_id, leg):
        t = self.next_ticket
        self.next_ticket += 1
        self.positions[t] = SimpleNamespace(ticket=t, symbol=symbol, volume=volume, price_open=self.prices[symbol],
                                            sl=sl, tp=tp, profit=0.0, comment=f"sig:{signal_id}:{leg}")
        return Opened(t, self.prices[symbol], volume)

    def open_manual(self, symbol, side, volume, sl, tp):
        return self.open_position(symbol, side, volume, sl, tp, 0, 1)

    def bot_positions(self):
        return list(self.positions.values())

    def position(self, ticket):
        return self.positions.get(ticket)

    def set_sltp(self, pos, sl=None, tp=None):
        self.calls.append(("sltp", pos.ticket, sl, tp))
        pos.sl = pos.sl if sl is None else sl
        pos.tp = pos.tp if tp is None else tp

    def move_sl_to_breakeven(self, pos):
        self.set_sltp(pos, sl=pos.price_open)

    def stop_distance_ok(self, symbol, level, side, is_sl):
        return not self.too_close

    # pending orders: the order ticket becomes the position ticket when it fills, as in MT5
    def place_limit(self, symbol, side, volume, price, sl, signal_id, leg):
        t = self.next_ticket
        self.next_ticket += 1
        self.orders[t] = SimpleNamespace(ticket=t, symbol=symbol, side=side, volume_current=volume,
                                         price_open=price, sl=sl, tp=0.0, comment=f"sig:{signal_id}:{leg}")
        return t

    def pending_order(self, ticket):
        return self.orders.get(ticket)

    def bot_orders(self):
        return list(self.orders.values())

    def cancel_order(self, order):
        self.calls.append(("cancel", order.ticket))
        del self.orders[order.ticket]

    def modify_order(self, order, price, sl):
        order.price_open, order.sl = price, sl

    def digits(self, symbol):
        return 2

    def fill(self, ticket):
        o = self.orders.pop(ticket)
        self.positions[ticket] = SimpleNamespace(ticket=ticket, symbol=o.symbol, volume=o.volume_current,
                                                 price_open=o.price_open, sl=o.sl, tp=0.0, profit=0.0,
                                                 comment=o.comment)

    def close_position(self, pos, volume=None):
        self.calls.append(("close", pos.ticket, volume))
        if volume is None or volume >= pos.volume:
            del self.positions[pos.ticket]
        else:
            pos.volume = round(pos.volume - volume, 8)


def make(dry=False):
    t, said, now = FakeTerminal(), [], [1000.0]
    c = Copier(t, Book(initial_balance=10_000.0, account="1001@PUPrime-Demo"), PROFILE, CONFIG, said.append, clock=lambda: now[0], dry=dry)
    return c, t, said, now


SIGNAL = "XAUUSD BUY @ 4151\nSL @ 4141\nTP1 @ 4170\nTP2 @ 4200"
SELL_SIGNAL = "XAUUSD SELL @ 4151\nSL @ 4161\nTP1 @ 4130\nTP2 @ 4100"


def test_signal_opens_one_leg_per_tp_each_with_full_risk():
    c, t, said, _ = make()
    c.on_message(CHAT, 10, None, SIGNAL)
    # 0.5 % of 10 000 = 50; 10 price units * 100 per lot -> 0.05 lots per leg
    assert [(p.volume, p.tp) for p in t.positions.values()] == [(0.05, 4170.0), (0.05, 4200.0)]
    assert c.book.get(10).legs == {"1": 1, "2": 2}
    assert "opened" in said[-1]


def test_repost_does_not_open_twice():
    c, t, said, now = make()
    c.on_message(CHAT, 10, None, SIGNAL)
    now[0] += 120
    c.on_message(CHAT, 11, None, SIGNAL)
    assert len(t.positions) == 2 and "repost" in said[-1]


def test_signal_without_tp_gets_two_legs_and_tps_later():
    c, t, said, now = make()
    c.on_message(CHAT, 10, None, "Gold buy @ 4151 sl @ 4141")
    assert [p.tp for p in t.positions.values()] == [0.0, 0.0]
    now[0] += 60
    c.on_message(CHAT, 11, None, "Tp1@4170 / Tp2@4200")
    assert [p.tp for p in t.positions.values()] == [4170.0, 4200.0]
    assert c.book.about["11"] == 10


def test_late_tps_on_the_wrong_side_are_not_set():
    c, t, said, _ = make()
    c.on_message(CHAT, 10, None, "Gold buy @ 4151 sl @ 4141")
    c.on_message(CHAT, 11, None, "Tp1@4100")
    assert [p.tp for p in t.positions.values()] == [0.0, 0.0] and "wrong side" in said[-1]


def test_price_run_away_is_not_chased():
    c, t, said, _ = make()
    t.prices["XAUUSD.s"] = 4155.0  # 40 pips against a 30 pip limit
    c.on_message(CHAT, 10, None, SIGNAL)
    assert not t.positions and "ran too far" in said[-1]


def test_unknown_symbol_and_rejected_signal_are_reported():
    c, t, said, _ = make()
    c.on_message(CHAT, 10, None, "GBPJPY buy @ 190 sl @ 189")
    assert "no tradable broker symbol" in said[-1]
    c.on_message(CHAT, 11, None, "Gold buy @ 4151 tp @ 4170")
    assert "no stop loss" in said[-1] and not t.positions


def test_close_half_closes_the_tp1_leg_then_breakeven_the_rest():
    c, t, said, _ = make()
    c.on_message(CHAT, 10, None, SIGNAL)
    c.on_message(CHAT, 12, 10, "Close half and set breakeven")
    assert list(t.positions) == [2] and t.positions[2].sl == 4151.0


def test_tp1_lock_at_pct_is_off_by_default_even_past_the_final_tp():
    c, t, said, _ = make()                              # CONFIG has no tp1_lock_at_pct -- other groups (NINJA)
    c.on_message(CHAT, 10, None, SIGNAL)
    c.on_message(CHAT, 11, 10, "Close half and set breakeven")
    t.prices["XAUUSD.s"] = 4199.0                       # almost at TP2 4200, way past 70 %
    c.watch()
    assert t.positions[2].sl == 4151.0


def test_tp1_locks_in_once_price_passes_pct_of_the_way_to_the_final_tp_buy():
    t, said, now = FakeTerminal(), [], [1000.0]
    c = Copier(t, Book(initial_balance=10_000.0, account=t.account), PROFILE,
               {**CONFIG, "tp1_lock_at_pct": 70}, said.append, clock=lambda: now[0])
    c.on_message(CHAT, 10, None, SIGNAL)                 # buy 4151, TP1 4170, TP2 (final) 4200
    c.on_message(CHAT, 11, 10, "Close half and set breakeven")
    assert t.positions[2].sl == 4151.0
    t.prices["XAUUSD.s"] = 4185.0                        # 69.4 % of the way to 4200 -- not yet
    c.watch()
    assert t.positions[2].sl == 4151.0
    t.prices["XAUUSD.s"] = 4185.5                        # 70.4 % -- locks to TP1
    c.watch()
    assert t.positions[2].sl == 4170.0 and "SL to TP1" in said[-1]
    c.watch()                                            # once: a second watch does not touch it again
    assert t.calls.count(("sltp", 2, 4170.0, None)) == 1


def test_tp1_locks_in_once_price_passes_pct_of_the_way_to_the_final_tp_sell():
    t, said, now = FakeTerminal(), [], [1000.0]
    t.prices["XAUUSD.s"] = 4151.0
    c = Copier(t, Book(initial_balance=10_000.0, account=t.account), PROFILE,
               {**CONFIG, "tp1_lock_at_pct": 70}, said.append, clock=lambda: now[0])
    c.on_message(CHAT, 10, None, SELL_SIGNAL)            # sell 4151, TP1 4130, TP2 (final) 4100
    c.on_message(CHAT, 11, 10, "Close half and set breakeven")
    assert t.positions[2].sl == 4151.0
    t.prices["XAUUSD.s"] = 4116.0                        # 68.6 % of the way to 4100 -- not yet
    c.watch()
    assert t.positions[2].sl == 4151.0
    t.prices["XAUUSD.s"] = 4115.0                        # 70.6 % -- locks to TP1
    c.watch()
    assert t.positions[2].sl == 4130.0 and "SL to TP1" in said[-1]


def test_breakeven_too_close_is_retried_by_the_watchdog():
    c, t, said, _ = make()
    c.on_message(CHAT, 10, None, SIGNAL)
    t.too_close = True
    c.on_message(CHAT, 12, 10, "SL to BE")
    assert c.book.pending_be == [1, 2] and t.positions[1].sl == 4141.0
    t.too_close = False
    c.watch()
    assert not c.book.pending_be and t.positions[1].sl == t.positions[2].sl == 4151.0


def test_exit_at_be_moves_sl_in_profit_and_tp_in_loss():
    c, t, said, _ = make()
    c.on_message(CHAT, 10, None, SIGNAL)
    t.positions[1].profit, t.positions[2].profit = 5.0, -5.0
    c.on_message(CHAT, 12, 10, "exit at be")
    assert t.positions[1].sl == 4151.0 and t.positions[2].tp == 4151.0


def test_command_without_reply_and_two_open_signals_does_nothing():
    c, t, said, now = make()
    c.on_message(CHAT, 10, None, SIGNAL)
    t.prices["EURUSD.s"] = 1.1000
    c.on_message(CHAT, 11, None, "EURUSD buy @ 1.1000 sl @ 1.0990 tp @ 1.1030")
    c.on_message(CHAT, 12, None, "Close all now")
    assert len(t.positions) == 3 and "not guessing" in said[-1]


def test_loss_stop_closes_everything_and_blocks_until_tomorrow():
    c, t, said, now = make()
    c.on_message(CHAT, 10, None, SIGNAL)
    t.equity = 9_590.0  # below the daily floor 10 000 - 4 % of 10 000
    c.watch()
    assert not t.positions and "LOSS STOP" in said[-1]
    assert c.book.halted(now[0]) and c.book.halt_until is not None
    t.equity = None
    c.on_message(CHAT, 20, None, SIGNAL.replace("BUY", "buy"))
    now[0] += 3600
    c.on_message(CHAT, 21, None, SIGNAL)
    assert not t.positions and "trading stopped" in said[-1]


def test_overall_stop_blocks_for_good():
    c, t, said, now = make()
    t.equity = 9_100.0
    c.watch()
    assert c.book.halt_until is None and c.book.halted(now[0] + 10 * 86400)


def test_dry_run_reports_and_sends_nothing():
    c, t, said, _ = make(dry=True)
    c.on_message(CHAT, 10, None, SIGNAL)
    assert not t.positions and said[-1].startswith("[DRY]") and "would open 2 x 0.05" in said[-1]
    assert not c.book.signals


def test_other_account_in_mt5_blocks_trades_and_loss_stop_until_it_is_back():
    c, t, said, now = make()
    t.account = "2002@RoboForex-Cent"
    c.on_message(CHAT, 10, None, SIGNAL)
    assert not t.positions and "ACCOUNT CHANGED" in said[-2] and "ignored" in said[-1]
    t.equity = 1.0  # would be a loss stop -- but not this book's account
    c.watch()
    assert not c.book.halt_reason
    t.account, t.equity = "1001@PUPrime-Demo", None
    c.on_message(CHAT, 11, None, SIGNAL)
    assert "trading again" in said[-2] and len(t.positions) == 2


def test_one_state_file_per_account(tmp_path):
    assert state_path(tmp_path, "1001@PUPrime-Demo") == tmp_path / "state_1001_PUPrime_Demo.json"


def test_fixed_lot_opens_every_leg_with_that_size_whatever_the_balance():
    t, said, now = FakeTerminal(), [], [1000.0]
    t.balance = 100.0
    small = RiskProfile(0.5, 40.0, 80.0, {"XAUUSD": 30}, 5)
    c = Copier(t, Book(initial_balance=100.0, account=t.account), small,
               {**CONFIG, "sizing": "fixed_lot", "fixed_lot": 0.01}, said.append, clock=lambda: now[0])
    c.on_message(CHAT, 10, None, SIGNAL)
    assert [p.volume for p in t.positions.values()] == [0.01, 0.01]


def test_fixed_lot_still_respects_the_loss_stops():
    t, said = FakeTerminal(), []
    t.balance = 100.0
    c = Copier(t, Book(initial_balance=100.0, account=t.account), PROFILE,  # 4 % of 100 = 4
               {**CONFIG, "sizing": "fixed_lot", "fixed_lot": 0.01}, said.append, clock=lambda: 1000.0)
    c.on_message(CHAT, 10, None, SIGNAL)  # 2 x 0.01 lot x 10 points x 100 = 20 at SL
    assert not t.positions and "daily stop" in said[-1]


def test_unknown_sizing_is_refused_at_start():
    import pytest
    with pytest.raises(ValueError, match="sizing"):
        Copier(FakeTerminal(), Book(), PROFILE, {**CONFIG, "sizing": "lots"}, print)
    with pytest.raises(ValueError, match="fixed_lot"):
        Copier(FakeTerminal(), Book(), PROFILE, {**CONFIG, "sizing": "fixed_lot"}, print)


def test_now_signal_opens_at_market_despite_drift():
    # #4910: "Sell EURUSD Now@1.12133" arrived with price at 1.12005 -- 12.8 pips
    c, t, said, _ = make()
    t.prices["EURUSD.s"] = 1.12005
    c.on_message(CHAT, 4910, None, "Sell EURUSD Now@1.12133\nSl @ 1.12327\nTp1@1.11800\nTp2@1.11128")
    assert len(t.positions) == 2 and "opened" in said[-1]


def test_now_signal_past_tp1_or_sl_is_still_refused():
    c, t, said, _ = make()
    t.prices["EURUSD.s"] = 1.11790
    c.on_message(CHAT, 4910, None, "Sell EURUSD Now@1.12133\nSl @ 1.12327\nTp1@1.11800\nTp2@1.11128")
    assert not t.positions and "past TP1" in said[-1]
    t.prices["EURUSD.s"] = 1.12400
    c.on_message(CHAT, 4911, None, "Sell EURUSD Now@1.12133\nSl @ 1.12327\nTp1@1.11800")
    assert not t.positions and "beyond the SL" in said[-1]


def test_signal_without_now_keeps_the_deviation_limit():
    c, t, said, _ = make()
    t.prices["EURUSD.s"] = 1.12005
    c.on_message(CHAT, 4912, None, "Sell EURUSD @1.12133\nSl @ 1.12327\nTp1@1.11800")
    assert not t.positions and "ran too far" in said[-1]


def test_a_missed_signal_is_not_opened_late():
    c, t, said, now = make()
    c.on_message(CHAT, 10, None, SIGNAL, posted_at=now[0] - 15 * 60)  # handed over on reconnect
    assert not t.positions and "missed" in said[-1]
    c.on_message(CHAT, 11, None, SIGNAL.replace("4141", "4140"), posted_at=now[0] - 20)  # fresh: within a minute
    assert len(t.positions) == 2


def test_replies_to_open_trades_are_followed_even_late():
    c, t, said, now = make()
    c.on_message(CHAT, 10, None, SIGNAL, posted_at=now[0])
    c.on_message(CHAT, 12, 10, "Close all now", posted_at=now[0] - 15 * 60)
    assert not t.positions


def test_commands_pause_blocks_new_trades_resume_lifts_it_close_all_empties():
    c, t, said, now = make()
    assert c.command("pause") == "paused" and c.command("pause") == "already paused"
    c.on_message(CHAT, 1, None, SIGNAL)
    assert t.positions == {} and "trading stopped" in said[-1]
    assert c.command("resume").startswith("resumed")
    c.on_message(CHAT, 2, None, SIGNAL)
    assert t.positions
    assert c.command("close_all").startswith("CLOSE ALL by Brano: 2 positions")
    assert t.positions == {} and c.command("explode") == "unknown command explode"


def test_every_signal_records_how_late_it_came_and_how_far_price_ran():
    c, t, said, now = make()
    t.price_at = lambda symbol, side, ts: 4148.0        # the quote when the group posted
    c.on_message(CHAT, 10, None, SIGNAL, posted_at=now[0] - 7.5)
    tm = c.book.timings[-1]
    assert tm["delay_s"] == 7.5 and tm["outcome"] == "opened"
    assert tm["price_posted"] == 4148.0 and tm["drift_pips"] is not None and tm["entry_gap_pips"] is not None
    c.on_message(CHAT, 11, None, "XAUUSD SELL @ 4200\nSL @ 4210\nTP1 @ 4180", posted_at=now[0] - 2)
    assert "not traded" in c.book.timings[-1]["outcome"]     # refused: price ran too far -- and why is kept


def test_a_failing_measurement_never_costs_the_trade():
    c, t, said, now = make()
    t.price_at = lambda *a: (_ for _ in ()).throw(RuntimeError("no ticks"))
    c.on_message(CHAT, 10, None, SIGNAL, posted_at=now[0] - 3)
    assert len(t.positions) == 2 and c.book.timings[-1]["delay_s"] == 3


def test_risk_can_differ_per_symbol_on_one_account():
    c, t, said, _ = make()
    c.config = {**c.config, "risk": {**c.config.get("risk", {}), "risk_per_symbol_pct": {"XAUUSD": 1.0}}}
    c.on_message(CHAT, 10, None, SIGNAL)
    # 1 % of 10 000 = 100 instead of 50 -> twice the lots of the default 0.5 %
    assert [p.volume for p in t.positions.values()] == [0.1, 0.1]
    assert c._risk_pct("BTCUSD") == c.profile.risk_per_position_pct


def test_one_position_is_closed_by_its_ticket_and_only_the_copiers_own():
    c, t, said, now = make()
    c.on_message(CHAT, 1, None, SIGNAL)
    first, second = sorted(t.positions)
    assert c.command(f"close:{first}") == f"closed #{first}"
    assert list(t.positions) == [second] and "CLOSED by Brano" in said[-1]
    assert "not open" in c.command("close:999999")


def test_muted_trade_reports_stay_quiet_but_trouble_gets_through(monkeypatch):
    from signal_copier import copier as cp
    sent = []
    bot = cp.BotNotifier.__new__(cp.BotNotifier)
    bot.prefix, bot.push_url, bot.q = "", None, type("Q", (), {"put": lambda self, t: sent.append(t)})()
    monkeypatch.setitem(cp.QUIET, "on", True)
    bot("#10 XAUUSD: SL to entry 4151")
    bot("watchdog ERROR KeyError: x")
    monkeypatch.setitem(cp.QUIET, "on", False)
    bot("closed #3")
    assert sent == ["watchdog ERROR KeyError: x", "closed #3"]


def test_by_hand_from_the_chart_sl_tp_move_and_a_trade_opens_within_the_lot_cap():
    c, t, said, now = make()
    c.on_message(CHAT, 1, None, SIGNAL)
    first = sorted(t.positions)[0]
    assert c.command(f"sltp:{first}:4150.5:") .startswith(f"#{first}: SL 4150.5")
    assert t.positions[first].sl == 4150.5 and "SL/TP by Brano" in said[-1]
    out = c.command("open:XAUUSD.s:buy:0.05:4100:4160")
    assert out.startswith("opened #") and "OPENED by Brano" in said[-1]
    c.config["manual_max_lots"] = 1.0                                         # a cap only when a profile sets one
    assert "outside" in c.command("open:XAUUSD.s:buy:5:4100:4160")
    c.command("pause")
    assert "trading is stopped" in c.command("open:XAUUSD.s:sell:0.05::")
