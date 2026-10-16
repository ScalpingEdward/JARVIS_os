from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.watchlist.models import WatchlistIn
from app.watchlist.service import watchlist_service

client = TestClient(app)
NOW = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)


def setup_function() -> None:
    watchlist_service.reset()


def _snapshot():
    return {"captured_at": NOW.isoformat(), "items": [
        {"name": "Gold", "symbol": "XAUUSD.s", "category": "Rohstoffe", "top": 2, "price": 4178.2,
         "change_pct": 0.19, "from_high_pct": -25.4, "notes": ["25 % unter dem 52-Wochen-Hoch"], "spark": [1, 2, 3]},
        {"name": "Siemens", "symbol": None, "category": "Aktien"},
    ]}


def test_push_and_read_back_the_latest_snapshot():
    assert client.get("/v1/watchlist").json()["items"] == []
    assert client.post("/v1/watchlist/snapshot", json=_snapshot()).status_code == 200
    body = client.get("/v1/watchlist").json()
    assert [i["name"] for i in body["items"]] == ["Gold", "Siemens"] and body["stale"] is False
    assert body["items"][1]["price"] is None   # no data source yet, still listed


def test_snapshot_goes_stale_when_the_feed_stops():
    watchlist_service.push(WatchlistIn(**_snapshot()), now=NOW)
    assert watchlist_service.get(NOW + timedelta(minutes=2)).stale is False
    assert watchlist_service.get(NOW + timedelta(minutes=6)).stale is True


import pytest

from app.watchlist.alerts import conditions
from app.watchlist.models import ReasonIn, WatchItem


@pytest.fixture(autouse=True)
def _alerts(monkeypatch):
    sent: list[list[str]] = []
    monkeypatch.setattr(watchlist_service, "alert", sent.append)
    return sent


def _item(**kw):
    base = dict(name="NVIDIA", symbol="NVIDIA", category="Aktien", price=200.0, change_pct=-1.0,
                vs_sma200_pct=2.0, rsi14=40.0, low_52w=150.0)
    base.update(kw)
    return WatchItem(**base)


def test_conditions_fire_on_the_change_not_on_the_state():
    old, new = _item(), _item(change_pct=-3.4, vs_sma200_pct=-0.5, rsi14=28.0)
    assert [c for c, _ in conditions(new, old)] == ["drop", "below200", "oversold"]
    assert conditions(new, new) == []                                  # still below: no new message
    assert [c for c, _ in conditions(_item(price=152.0), _item(price=170.0))] == ["near_low"]
    assert conditions(_item(category="Krypto", change_pct=-4.0), _item(category="Krypto")) == []  # crypto's bar is -5 %


def test_each_alert_goes_out_once_a_day(_alerts):
    snap = lambda **kw: WatchlistIn(captured_at=NOW, items=[_item(**kw)])
    watchlist_service.push(snap(), now=NOW)
    watchlist_service.push(snap(change_pct=-4.0), now=NOW + timedelta(minutes=1))
    watchlist_service.push(snap(change_pct=-1.0), now=NOW + timedelta(minutes=2))
    watchlist_service.push(snap(change_pct=-4.5), now=NOW + timedelta(minutes=3))   # same day: not again
    sent = [line for batch in _alerts for line in batch]
    assert len(sent) == 1 and "NVIDIA" in sent[0] and "heute" in sent[0]


def test_reasons_and_analysis_are_kept_with_the_symbol():
    watchlist_service.push(WatchlistIn(**_snapshot()), now=NOW)
    watchlist_service.set_reason("Gold", ReasonIn(reason="Krisenschutz, Zentralbanken kaufen", recommended_by="Marek"))
    seen = {}

    def writer(item, reason, by):
        seen.update(item=item.name, reason=reason, by=by)
        return "Was es ist: Edelmetall."
    item = watchlist_service.analyse("Gold", writer=writer)
    assert seen == {"item": "Gold", "reason": "Krisenschutz, Zentralbanken kaufen", "by": "Marek"}
    got = {i["name"]: i for i in client.get("/v1/watchlist").json()["items"]}["Gold"]
    assert got["reason"].startswith("Krisenschutz") and got["analysis"] == "Was es ist: Edelmetall." and got["analysis_at"]
    assert item.recommended_by == "Marek"


def test_unknown_symbol_is_404():
    watchlist_service.push(WatchlistIn(**_snapshot()), now=NOW)
    assert client.put("/v1/watchlist/reasons/Nope", json={"reason": "x"}).status_code == 404
