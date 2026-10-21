from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.copier_status.models import CopierState, CopierStatusIn
from app.copier_status.service import copier_status_service
from app.main import app

client = TestClient(app)
NOW = datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc)


def setup_function() -> None:
    copier_status_service.reset()


def _status(profile="puprime_demo", currency="EUR", balance=10_000.0, groups=None, login=700167790):
    return {
        "profile": profile, "account_login": login, "server": "PUPrime-Demo", "currency": currency,
        "balance": balance, "equity": balance + 20, "captured_at": NOW.isoformat(),
        "groups": groups if groups is not None else [
            {"name": "ICT CRT PREMIUM", "pnl_today": 40.0, "pnl_week": 30.0, "pnl_total": 120.0,
             "closed_trades": 4, "open_positions": 1, "open_pnl": 20.0},
            {"name": "(not from a signal)", "pnl_total": -73.8, "closed_trades": 1},
        ],
        "open_positions": [{"ticket": 1, "symbol": "XAUUSD.s", "side": "buy", "volume": 0.05,
                            "price_open": 4151, "sl": 4141, "tp": 4200, "profit": 20.0, "group": "ICT CRT PREMIUM"}],
    }


def test_push_keeps_only_the_latest_status_per_profile():
    assert client.post("/v1/copier/status", json=_status(balance=9_000)).status_code == 200
    assert client.post("/v1/copier/status", json=_status(balance=9_500)).status_code == 200
    listed = client.get("/v1/copier/status").json()
    assert len(listed) == 1 and listed[0]["balance"] == 9_500 and listed[0]["state"] == "live"


def test_overview_adds_up_per_currency_and_per_group_across_accounts():
    client.post("/v1/copier/status", json=_status())
    client.post("/v1/copier/status", json=_status("roboforex_live", balance=5_000, login=1, groups=[
        {"name": "ICT CRT PREMIUM", "pnl_today": -10.0, "pnl_week": -10.0, "pnl_total": 80.0}]))
    client.post("/v1/copier/status", json=_status("cent", currency="USC", balance=100_000, login=2, groups=[]))
    o = client.get("/v1/copier/overview").json()
    eur = next(t for t in o["totals"] if t["currency"] == "EUR")
    assert (eur["accounts"], eur["balance"], eur["pnl_today"], eur["pnl_total"]) == (2, 15_000, 30.0, 126.2)
    assert [t["currency"] for t in o["totals"]] == ["EUR", "USC"]
    ict = next(g for g in o["groups"] if g["name"] == "ICT CRT PREMIUM")
    assert ict["pnl_total"] == 200.0 and sorted(ict["accounts"]) == ["puprime_demo", "roboforex_live"]


def test_state_turns_stale_then_offline_when_pushes_stop():
    copier_status_service.push(CopierStatusIn(**_status()), now=NOW)
    assert copier_status_service.list(NOW + timedelta(minutes=1))[0].state == CopierState.live
    assert copier_status_service.list(NOW + timedelta(minutes=4))[0].state == CopierState.stale
    assert copier_status_service.list(NOW + timedelta(minutes=11))[0].state == CopierState.offline


def test_bad_profile_name_is_refused_and_forget_removes_it():
    assert client.post("/v1/copier/status", json=_status("Bad Name")).status_code == 422
    client.post("/v1/copier/status", json=_status())
    assert client.delete("/v1/copier/status/puprime_demo").status_code == 204
    assert client.delete("/v1/copier/status/puprime_demo").status_code == 404
    assert client.get("/v1/copier/status").json() == []


def test_history_keeps_one_point_every_five_minutes_and_forgets_after_thirty_days():
    base = NOW - timedelta(days=31)
    copier_status_service.push(CopierStatusIn(**_status(balance=900)), now=base)
    for minute in range(0, 12):  # a push every minute for 12 minutes
        copier_status_service.push(CopierStatusIn(**_status(balance=1000 + minute)), now=NOW + timedelta(minutes=minute))
    points = copier_status_service.history(hours=24, now=NOW + timedelta(minutes=12))["puprime_demo"]
    assert [p.balance for p in points] == [1000, 1005, 1010]
    assert copier_status_service.history(hours=24 * 40, now=NOW + timedelta(minutes=12))["puprime_demo"][0].balance == 1000


def test_history_endpoint():
    client.post("/v1/copier/status", json=_status())
    body = client.get("/v1/copier/history?hours=1").json()
    assert body["puprime_demo"][0]["equity"] == 10_020


def test_live_numbers_are_kept_in_memory_and_only_while_fresh(monkeypatch):
    from app.copier_status import api
    api._live.clear()
    api.push_live(api.LiveIn(profile="demo", balance=1000, equity=1012.5, positions=[{"ticket": 7, "profit": 12.5}]))
    assert api.live() == {"demo": {"balance": 1000, "equity": 1012.5, "positions": {"7": 12.5}, "age_s": 0.0}}
    t = api.time.monotonic() + api.LIVE_FOR_S + 1
    monkeypatch.setattr(api.time, "monotonic", lambda: t)
    assert api.live() == {}


def test_an_open_chart_asks_its_copier_for_candles_until_it_is_closed(monkeypatch):
    from app.copier_status import api
    api._chart_wanted.clear(); api._rates.clear()
    live = api.LiveIn(profile="demo", balance=1, equity=1)
    assert api.push_live(live) == {"want_rates": []}
    assert api.chart("demo", "XAUUSD.s") == {"bars": [], "pending": True}
    assert api.push_live(live) == {"want_rates": ["XAUUSD.s"]}
    assert api.push_live(api.LiveIn(profile="other", balance=1, equity=1)) == {"want_rates": []}
    api.push_rates(api.RatesIn(profile="demo", symbol="XAUUSD.s", bars=[[1, 2, 3, 1, 2]]))
    assert api.chart("demo", "XAUUSD.s")["bars"] == [[1, 2, 3, 1, 2]]
    t = api.time.monotonic() + api.CHART_FOR_S + 1
    monkeypatch.setattr(api.time, "monotonic", lambda: t)
    assert api.push_live(live) == {"want_rates": []}
