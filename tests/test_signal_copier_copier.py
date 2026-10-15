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
        return AccountState(initial or 10_000.0, 10_000.0, self.balance, eq, at_sl)

    def open_position(self, symbol, side, volume, sl, tp, signal_id, leg):
        t = self.next_ticket
        self.next_ticket += 1
        self.positions[t] = SimpleNamespace(ticket=t, symbol=symbol, volume=volume, price_open=self.prices[symbol],
                                            sl=sl, tp=tp, profit=0.0, comment=f"sig:{signal_id}:{leg}")
        return Opened(t, self.prices[symbol], volume)

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
