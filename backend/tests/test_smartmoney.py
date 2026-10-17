from datetime import datetime, timedelta, timezone

import httpx

from app.smartmoney import macro, service as svc
from app.smartmoney.insider import clusters, parse_form4
from app.smartmoney.service import smart_money_service

FORM4 = """<?xml version="1.0"?><ownershipDocument>
<reportingOwner><reportingOwnerId><rptOwnerName>Huang Jen Hsun</rptOwnerName></reportingOwnerId>
<reportingOwnerRelationship><isDirector>1</isDirector><officerTitle>President and CEO</officerTitle></reportingOwnerRelationship></reportingOwner>
<nonDerivativeTable>
 <nonDerivativeTransaction><transactionDate><value>{day}</value></transactionDate>
  <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
  <transactionAmounts><transactionShares><value>1000</value></transactionShares><transactionPricePerShare><value>150.5</value></transactionPricePerShare></transactionAmounts></nonDerivativeTransaction>
 <nonDerivativeTransaction><transactionDate><value>{day}</value></transactionDate>
  <transactionCoding><transactionCode>M</transactionCoding></transactionCoding>
  <transactionAmounts><transactionShares><value>5000</value></transactionShares><transactionPricePerShare><value>0</value></transactionPricePerShare></transactionAmounts></nonDerivativeTransaction>
</nonDerivativeTable></ownershipDocument>"""


def _day(n=0):
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime("%Y-%m-%d")


def test_form4_keeps_only_open_market_buys_and_sales():
    xml = FORM4.format(day=_day()).replace("<transactionCode>M</transactionCoding>", "<transactionCode>M</transactionCode>")
    trades = parse_form4(xml)
    assert len(trades) == 1   # the option exercise (M) is no view on the stock
    t = trades[0]
    assert (t["owner"], t["title"], t["code"], t["shares"], t["value"]) == ("Huang Jen Hsun", "President and CEO", "P", 1000, 150500)


def test_cluster_needs_two_different_buyers_recently():
    now = datetime.now(timezone.utc)
    tr = lambda o, c="P", d=1: {"ticker": "NVDA", "owner": o, "code": c, "traded_on": now - timedelta(days=d)}  # noqa: E731
    assert clusters([tr("A"), tr("A")]) == {}
    assert clusters([tr("A"), tr("B", d=20)]) == {}
    assert clusters([tr("A"), tr("B", "S")]) == {}
    assert clusters([tr("A"), tr("B")]) == {"NVDA": ["A", "B"]}


def test_macro_keeps_high_impact_of_our_currencies_and_alerts_once(monkeypatch):
    soon = (datetime.now(timezone.utc) + timedelta(minutes=29)).isoformat()
    later = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    feed = [{"title": "CPI m/m", "country": "USD", "date": soon, "impact": "High", "forecast": "0.3%", "previous": "0.4%"},
            {"title": "Retail Sales", "country": "USD", "date": later, "impact": "Medium"},
            {"title": "Cash Rate", "country": "AUD", "date": later, "impact": "High"}]
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=feed)))
    monkeypatch.setattr(macro, "_cache", (0.0, []))
    evts = macro.events(client=c)
    assert [e["title"] for e in evts] == ["CPI m/m"] and evts[0]["title_de"] == "Inflation"
    smart_money_service.reset()
    sent = []
    monkeypatch.setattr(svc.SmartMoneyService, "_telegram", staticmethod(lambda title, text: sent.append(title)))
    assert smart_money_service.macro_tick() == 1
    assert smart_money_service.macro_tick() == 0   # once
    assert sent == ["Makro in 30 Minuten"]


class FakeSec:
    def configured(self):
        return True

    def cik(self, ticker):
        return 1045810 if ticker == "NVDA" else None

    def recent_form4(self, cik, since):
        return [{"acc": "0001-26-000001", "doc": "f4.xml", "filed": datetime.now(timezone.utc)}]

    def form4(self, cik, acc, doc):
        return FORM4.format(day=_day()).replace("<transactionCode>M</transactionCoding>", "<transactionCode>M</transactionCode>")


def test_insider_poll_stores_alerts_big_buys_and_reads_each_filing_once(monkeypatch):
    smart_money_service.reset()
    monkeypatch.setattr(smart_money_service, "sec", FakeSec())
    monkeypatch.setattr(macro, "events", lambda: [])   # no network in tests
    sent = []
    monkeypatch.setattr(svc.SmartMoneyService, "_telegram", staticmethod(lambda title, text: sent.append((title, text))))
    assert smart_money_service.poll_insiders() == {"new": 1, "error": ""}
    assert smart_money_service.poll_insiders() == {"new": 0, "error": ""}
    assert [s[0] for s in sent] == ["Insider-Kauf"] and "NVIDIA (NVDA)" in sent[0][1]
    o = smart_money_service.overview()
    assert o["insider"][0]["ticker"] == "NVDA" and o["insider"][0]["value"] == 150500
