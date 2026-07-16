from fastapi.testclient import TestClient

from app.live_integrations.service import live_integration_service
from app.main import app


client = TestClient(app)


def setup_function() -> None:
    live_integration_service.reset()


def test_creates_read_only_mt5_integration_and_tracks_heartbeat() -> None:
    created = client.post(
        "/v1/live-integrations",
        json={
            "name": "MT5 Terminal 1",
            "kind": "mt5",
            "account_label": "FTMO read-only",
            "symbols": ["XAUUSD", "NAS100"],
            "read_only": True,
        },
    )
    assert created.status_code == 201
    integration_id = created.json()["id"]
    heartbeat = client.post(
        f"/v1/live-integrations/{integration_id}/heartbeat",
        json={"state": "online", "latency_ms": 18.5, "records_received": 42},
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["state"] == "online"
    status = client.get("/v1/live-integrations/status").json()
    assert status["online"] == 1
    assert status["records_received"] == 42


def test_rejects_write_enabled_connector() -> None:
    response = client.post(
        "/v1/live-integrations",
        json={"name": "Unsafe MT5", "kind": "mt5", "read_only": False},
    )
    assert response.status_code == 400
    assert "read-only" in response.json()["detail"]


def test_normalizes_and_filters_live_market_events() -> None:
    event = client.post(
        "/v1/live-integrations/events",
        json={
            "source": "tradingview",
            "symbol": "xauusd",
            "event_type": "alert",
            "timeframe": "H1",
            "price": 3345.2,
            "payload": {"message": "liquidity sweep"},
        },
    )
    assert event.status_code == 202
    assert event.json()["symbol"] == "XAUUSD"
    recent = client.get("/v1/live-integrations/events/recent?symbol=XAUUSD").json()
    assert len(recent) == 1
    assert recent[0]["event_type"] == "alert"


def test_safety_flags_remain_disabled() -> None:
    status = client.get("/v1/live-integrations/status").json()
    assert status["read_only_enforced"] is True
    assert status["automatic_order_execution"] is False
    assert status["automatic_merge"] is False
