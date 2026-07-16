from fastapi.testclient import TestClient

from app.main import app
from app.trade_analyst.service import trade_analyst_service

client = TestClient(app)


def setup_function() -> None:
    trade_analyst_service.reset()


def test_creates_favorable_trade_analysis() -> None:
    response = client.post(
        "/v1/trade-analyst/analyses",
        json={
            "symbol": "XAUUSD",
            "direction": "long",
            "current_price": 2400,
            "entry_zone": {"low": 2398, "high": 2401},
            "invalidation_price": 2390,
            "target_prices": [2420, 2435],
            "market_regime": "trending",
            "higher_timeframe_bias": "long",
            "structure_score": 0.9,
            "liquidity_score": 0.7,
            "orderflow_score": 0.8,
            "macro_risk": 0.1,
            "correlation_risk": 0.1,
            "data_quality": 0.95,
            "memory_edge": 0.6,
            "simulation_probability": 0.72,
            "factors": [{"name": "H1 liquidity sweep", "score": 0.8, "confidence": 0.9}],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["symbol"] == "XAUUSD"
    assert body["verdict"] == "favorable"
    assert body["confidence"] >= 0.55
    assert body["risk_reward"] > 1
    assert body["automatic_order_execution"] is False


def test_marks_low_quality_analysis_as_insufficient() -> None:
    response = client.post(
        "/v1/trade-analyst/analyses",
        json={
            "symbol": "BTCUSD",
            "direction": "short",
            "current_price": 60000,
            "data_quality": 0.2,
        },
    )
    assert response.status_code == 201
    assert response.json()["verdict"] == "insufficient_data"


def test_trade_analyst_safety_flags_remain_disabled() -> None:
    payload = client.get("/v1/trade-analyst/status").json()
    assert payload["automatic_order_execution"] is False
    assert payload["automatic_merge"] is False
