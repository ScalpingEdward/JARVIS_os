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
