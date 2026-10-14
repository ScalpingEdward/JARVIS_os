from signal_copier.book import Book, TrackedSignal, close_half_plan

CHAT = -100


def sig(msg_id, symbol="XAUUSD.s", side="buy", at=1000.0, tps=(4170.0, 4200.0), legs=None):
    return TrackedSignal(msg_id, CHAT, symbol, side, 4151, 4133, list(tps), at, legs or {"1": msg_id * 10 + 1, "2": msg_id * 10 + 2})


def test_reply_finds_signal_also_through_a_reply_chain():
    b = Book()
    b.add(sig(4890))
    b.link(4899, 4890)  # "Close half lots" answered #4890
    assert b.target(CHAT, 4890, None, set())[0].msg_id == 4890
    assert b.target(CHAT, 4899, None, set())[0].msg_id == 4890


def test_reply_to_unknown_message_is_not_guessed():
    s, why = Book().target(CHAT, 1234, None, {1})
    assert s is None and "no signal" in why


def test_no_reply_uses_symbol_or_the_only_open_signal():
    b = Book()
    b.add(sig(1, "XAUUSD.s"))
    b.add(sig(2, "EURUSD.s"))
    assert b.target(CHAT, None, "XAUUSD", {1, 2})[0].msg_id == 1
    assert b.target(CHAT, None, None, {1})[0].msg_id == 1
    s, why = b.target(CHAT, None, None, {1, 2})
    assert s is None and "not guessing" in why


def test_repost_within_window_is_the_same_trade():
    b = Book()
    b.add(sig(4250, at=1000.0, tps=()))
    assert b.repost_of(CHAT, "XAUUSD.s", "buy", 1000.0 + 60).msg_id == 4250
    assert b.repost_of(CHAT, "XAUUSD.s", "sell", 1060.0) is None
    assert b.repost_of(CHAT, "XAUUSD.s", "buy", 1000.0 + 3600) is None


def test_late_tps_go_to_the_latest_signal_without_tps():
    b = Book()
    b.add(sig(4716, at=1000.0, tps=()))
    assert b.awaiting_tps(CHAT, 1030.0).msg_id == 4716
    b.add(sig(4720, at=1100.0))  # a newer complete signal in between
    assert b.awaiting_tps(CHAT, 1130.0) is None


def test_book_survives_a_restart(tmp_path):
    b = Book(initial_balance=10_000)
    b.add(sig(1))
    b.link(5, 1)
    b.save(tmp_path / "state.json")
    again = Book.load(tmp_path / "state.json")
    assert again.get(1).legs == {"1": 11, "2": 12} and again.about["5"] == 1 and again.initial_balance == 10_000


def test_close_half_two_legs():
    legs = {"1": 11, "2": 12}
    assert close_half_plan(legs, {11, 12}, {}, 0.01, 0.01)[0] == [(11, None)]
    # TP1 already hit, or a second "close half" / "Partial filled": TP2 leg stays.
    plan, why = close_half_plan(legs, {12}, {}, 0.01, 0.01)
    assert plan == [] and "TP2 leg stays" in why


def test_close_half_one_leg_splits_volume():
    assert close_half_plan({"1": 11}, {11}, {11: 0.27}, 0.01, 0.01)[0] == [(11, 0.13)]
    assert close_half_plan({"1": 11}, {11}, {11: 0.01}, 0.01, 0.01)[0] == []
