import pytest

from signal_copier.parser import (
    BREAKEVEN, CLOSE_ALL, CLOSE_HALF, EXIT_AT_BE, Command, Rejected, Signal, TakeProfits, parse,
)

# Real messages from the channel, verbatim.
SIGNALS = [
    ("XAUUSD Buy Now @ 4151\nSl @ 4133\nTp1@4170\nTp2@4200",
     Signal("XAUUSD", "buy", 4151, 4133, (4170, 4200))),
    ("Sell NZDUSD now @0.56058\nSl@0.56152\nTp1@0.55970\nTp2@0.55777",
     Signal("NZDUSD", "sell", 0.56058, 0.56152, (0.55970, 0.55777))),
    ("Buy GBPUSD now @1.32095\nSl@1.31843\nTp-1@1.32400\nTp-2@1.32856",
     Signal("GBPUSD", "buy", 1.32095, 1.31843, (1.32400, 1.32856))),
    ("Sell NAS100(nasdaq) now @31,002\nSl@31,343\nTp-1@30,765\nTp-2@30,110",
     Signal("NAS100", "sell", 31002, 31343, (30765, 30110))),
    ("Sell USDCAD now @1.42317\nSl@1.42475\nTp-1@1.42138\nTp-2@1.41800",
     Signal("USDCAD", "sell", 1.42317, 1.42475, (1.42138, 1.41800))),
    ("Buy XAUUSD now @4124 Sl@4100 Tp-1@4143 Tp-2@4184",
     Signal("XAUUSD", "buy", 4124, 4100, (4143, 4184))),
]


@pytest.mark.parametrize("text,expected", SIGNALS)
def test_real_signals(text, expected):
    assert parse(text) == expected


COMMANDS = [
    ("Exit gold now at breakeven", {CLOSE_ALL}, "XAUUSD"),
    ("XAUUSD Tp done&dusted close half lots sl be now✅✅", {CLOSE_HALF, BREAKEVEN}, "XAUUSD"),
    ("Usdjpy close half profit and set sl breakeven and hold", {CLOSE_HALF, BREAKEVEN}, "USDJPY"),
    ("GBPUSD Done&dusted close half lots now set sl be", {CLOSE_HALF, BREAKEVEN}, "GBPUSD"),
    ("Close half lots sl be now", {CLOSE_HALF, BREAKEVEN}, None),
    ("Close some lots sl be", {CLOSE_HALF, BREAKEVEN}, None),
    ("Tp1 done&dusted close half lots sl be now", {CLOSE_HALF, BREAKEVEN}, None),
    ("Set Breakeven", {BREAKEVEN}, None),
]


@pytest.mark.parametrize("text,actions,symbol", COMMANDS)
def test_real_commands(text, actions, symbol):
    assert parse(text) == Command(frozenset(actions), symbol)


@pytest.mark.parametrize("text", ["NASDAQ and Tp1 Smashed..!!🩷", "Running 🔥", "Good morning traders"])
def test_commentary_is_no_action(text):
    assert parse(text) is None


@pytest.mark.parametrize("text,reason", [
    ("Buy EURUSD now @1.10000 Tp1@1.10500", "no stop loss -- risk cannot be sized"),
    ("Buy the dip, guys", None),  # no levels -> not a signal
    ("Buy EURUSD now @1.10000 Sl@1.10200 Tp1@1.10500", "buy needs sl < entry < tps"),
    ("Sell EURUSD now @1.10000 Sl@1.10200 Tp1@1.10500", "sell needs sl > entry > tps"),
    ("Buy now @1.10000 Sl@1.09800 Tp1@1.10500", "no symbol"),
])
def test_broken_signals_are_refused(text, reason):
    result = parse(text)
    if reason is None:
        assert result is None
    else:
        assert isinstance(result, Rejected) and result.reason == reason


WEEKLY_REPORT = """⚜️ICT VIP WEEKLY SIGNAL REPORT

•==========================•
✅XAUUSD           +550(3R)
✅GBPJPY            +225(3.2R)
✅XAUUSD           breakeven
✅NASDAQ           +460(2.2R)
🔴EURUSD            -20(1R)
⚜️NET PIPS__________    =+2630(18.4rr)"""


def test_weekly_report_is_not_a_breakeven_on_gold():
    # Seen live 2026-10-09 (#4882): the word "breakeven" in a result line.
    assert parse(WEEKLY_REPORT) is None


@pytest.mark.parametrize("text", [
    "React usdcad signal\nWas legit", "Done&dusted", "I was holding usdcad",
    "React EU signal if want XAUUSD 100% sure trade now", "-1r", "Usdcad tp2 smashed", "Tp1✅",
    "EU on #cpi News Done&Dusted..!!✅\n\n~EURUSD 1:3.5RR Tp2 Hit.!!✅👌",
])
def test_live_chatter_is_no_action(text):
    assert parse(text) is None


# From the 600-message replay (2026-10-14).

def test_typo_xausd_is_gold():
    assert parse("Sell XAUSD now@4520\nSl@4541\nTp1@4500\nTp2@4450") == Signal("XAUUSD", "sell", 4520, 4541, (4500, 4450))


def test_fast_signal_comes_in_two_messages():
    assert parse("Buy XAUUSD now@4310\nSl@4290") == Signal("XAUUSD", "buy", 4310, 4290, ())
    assert parse("Tp1@4330\nTp2@4380") == TakeProfits((4330, 4380))


LIVE_COMMANDS = [
    ("Exit at be", {EXIT_AT_BE}, None),
    ("Exit be", {EXIT_AT_BE}, None),
    ("Exit or when it comes to be", {EXIT_AT_BE}, None),
    ("~Set Breakeven or Exit at be\n-(due to Monday’s manipulation)", {EXIT_AT_BE}, None),
    ("Exit now at breakeven", {CLOSE_ALL}, None),
    ("Close full✅\nTp2 done&dusted", {CLOSE_ALL}, None),
    ("Close this trade in profit", {CLOSE_ALL}, None),
    ("Close half lots set be\nIf you’re holding the trade", {CLOSE_HALF, BREAKEVEN}, None),
    ("Close half lots set SL in profit zone✅", {CLOSE_HALF, BREAKEVEN}, None),
    ("Set Breakeven now and close 50% lots now", {CLOSE_HALF, BREAKEVEN}, None),
    ("NZDUSD Tp done&dusted ✅\nClose max lots and set sl to breakeven", {CLOSE_HALF, BREAKEVEN}, "NZDUSD"),
    ("Set BE here", {BREAKEVEN}, None),
    ("EU Set Breakeven", {BREAKEVEN}, "EURUSD"),
    ("Take partials", {CLOSE_HALF}, None),
]


@pytest.mark.parametrize("text,actions,symbol", LIVE_COMMANDS)
def test_live_history_commands(text, actions, symbol):
    assert parse(text) == Command(frozenset(actions), symbol)
