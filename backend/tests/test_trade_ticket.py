import pytest

from app.assistant import tools
from app.copier_status import commands, tickets

# gold at PU Prime: 0.01 tick, 1 EUR per tick per lot (made-up but the right shape)
Q = {"symbol": "XAUUSD.s", "bid": 4050.0, "ask": 4050.3, "tick_size": 0.01, "tick_value": 1.0,
     "vol_min": 0.01, "vol_max": 100, "vol_step": 0.01, "digits": 2}


class Acc:
    profile, label, currency, balance, state = "demo", "ICT CRT", "EUR", 10000.0, "live"


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(tickets, "_account", lambda account=None: Acc())
    monkeypatch.setattr(tickets, "_quote", lambda profile, symbol, wait_s=12: dict(Q))
    import app.dashboard_layout.ui as ui
    monkeypatch.setattr(ui, "_symbol", lambda name: "XAUUSD.s")
    monkeypatch.setattr(tools, "_external_at", 0.0)
    sent = []
    monkeypatch.setattr(commands, "create", lambda profile, action, source, confirmed=False, label="": sent.append(action) or {"id": str(len(sent))})
    tickets._ticket = None
    yield sent


def test_lots_follow_the_risk_and_split_over_the_targets():
    t = tickets.prepare("Gold", "buy", 4040.3, [4070.3, 4090.3], risk_pct=1)
    # 10 points to the stop = 1000 ticks x 1 EUR = 1000 EUR per lot; 1 % of 10 000 = 100 EUR -> 0.10 lots
    assert t["lots"] == 0.1 and [l["lots"] for l in t["legs"]] == [0.05, 0.05]
    assert t["risk_money"] == 100.0 and t["rr"] == [2.0, 4.0]


def test_wrong_sides_and_limits_are_refused():
    with pytest.raises(tickets.TicketError):
        tickets.prepare("Gold", "buy", 4060, [4080])          # stop above the price of a buy
    assert tickets.prepare("Gold", "buy", 4040, [4080], risk_pct=3)["lots"] > 0     # his risk, no limit of ours
    assert tickets.prepare("Gold", "buy", 4040, [4080], lots=1.5)["lots"] == 1.5
    with pytest.raises(tickets.TicketError):
        tickets.prepare("Gold", "buy", 4040, [4080], lots=150)                       # above the broker's maximum


def test_it_opens_only_on_his_own_order(setup):
    tools.run("trade_ticket", {"action": "prepare", "symbol": "Gold", "side": "buy", "sl": 4040.3, "tps": [4070.3]})
    out, _ = tools.run("trade_ticket", {"action": "open"}, "dashboard", said="zeig mir den Chart von Gold")
    assert "nicht gesagt" in out and setup == []
    out, _ = tools.run("trade_ticket", {"action": "open", "_said": "eröffne jetzt"}, "dashboard", said="öffne den Chart")
    assert setup == []                                       # AURON cannot slip the words in himself
    out, _ = tools.run("trade_ticket", {"action": "open"}, "telegram", said="eröffne jetzt")
    assert setup == []
    out, _ = tools.run("trade_ticket", {"action": "open"}, "dashboard", said="Ok, eröffne jetzt")
    assert '"ok": true' in out and setup == ["open:XAUUSD.s:buy:0.1:4040.3:4070.3"]
    out, _ = tools.run("trade_ticket", {"action": "open"}, "dashboard", said="eröffne nochmal")
    assert len(setup) == 1                                    # a ticket opens once


def test_after_a_mail_only_his_click_opens(setup, monkeypatch):
    tickets.prepare("Gold", "sell", 4060.0, [4030.0])
    monkeypatch.setattr(tools, "_external_at", __import__("time").time())
    out, _ = tools.run("trade_ticket", {"action": "open"}, "dashboard", said="eröffne jetzt")
    assert "waiting_for_brano" in out and setup == []
    tickets.open_ticket("click")
    assert setup == ["open:XAUUSD.s:sell:0.1:4060.0:4030.0"]


def test_plain_open_words():
    w = tickets.OPEN_WORDS.search
    assert w("Eröffne jetzt") and w("open it") and w("öffne den Trade jetzt") and w("führ ihn aus")
    assert not w("öffne den Chart von Gold") and not w("zeig mir Gold")


def test_quick_order_in_pips_opens_at_once(setup):
    out, _ = tools.run("trade_ticket", {"action": "open_now", "symbol": "Gold", "side": "buy", "lots": 0.2, "tp_pips": [100]},
                       "dashboard", said="Auron, öffne schnell eine Position in Gold, 0,2 Lot, TP 100 Pips, jetzt")
    assert '"ok": true' in out and setup == ["open:XAUUSD.s:buy:0.2::4060.3"]      # 100 pips of gold = 10.00
    out, _ = tools.run("trade_ticket", {"action": "open_now", "symbol": "Gold", "side": "sell", "lots": 0.2, "sl_pips": 50},
                       "dashboard", said="zeig mir Gold")
    assert "nicht gesagt" in out and len(setup) == 1


def test_risk_in_money_and_targets_as_rr():
    t = tickets.prepare("Gold", "buy", 0, [], risk_money=200, sl_pips=100, rr=[2, 3])
    # 100 pips = 10.00 -> 1000 EUR per lot; 200 EUR -> 0.20 lots; targets 2 R and 3 R from 4050.30
    assert t["sl"] == 4040.3 and t["tps"] == [4070.3, 4080.3] and t["lots"] == 0.2 and t["risk_money"] == 200.0
