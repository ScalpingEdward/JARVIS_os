from fastapi.testclient import TestClient

from app.main import app
from app.orderflow.service import orderflow_service

client = TestClient(app)


def setup_function() -> None:
    orderflow_service.reset()


def test_calculates_delta_imbalances_and_signal() -> None:
    payload = {
        "symbol": "XAUUSD",
        "source": "futures_exchange",
        "levels": [
            {"price": 2400.0, "bid_volume": 10, "ask_volume": 50, "resting_bid": 5, "resting_ask": 10},
            {"price": 2400.5, "bid_volume": 20, "ask_volume": 70, "resting_bid": 10, "resting_ask": 20},
            {"price": 2401.0, "bid_volume": 15, "ask_volume": 45, "resting_bid": 8, "resting_ask": 12},
        ],
        "cumulative_delta": 120,
        "open_interest": 1000,
        "previous_open_interest": 950,
    }
    response = client.post("/v1/orderflow/snapshots", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["delta"] == 120
    assert body["signal"] == "bullish"
    assert len(body["stacked_buy_imbalances"]) == 3
    assert body["open_interest_change"] == 50


def test_detects_absorption_and_latest_snapshot() -> None:
    payload = {
        "symbol": "BTCUSD",
        "source": "crypto_exchange",
        "levels": [
            {"price": 60000, "bid_volume": 10, "ask_volume": 10, "resting_bid": 100, "resting_ask": 5}
        ],
    }
    created = client.post("/v1/orderflow/snapshots", json=payload)
    assert created.status_code == 201
    assert created.json()["signal"] == "absorption_buy"
    latest = client.get("/v1/orderflow/latest/btcusd")
    assert latest.status_code == 200
    assert latest.json()["symbol"] == "BTCUSD"


def test_orderflow_safety_flags_remain_disabled() -> None:
    status = client.get("/v1/orderflow/status").json()
    assert status["automatic_order_execution"] is False
    assert status["automatic_merge"] is False
