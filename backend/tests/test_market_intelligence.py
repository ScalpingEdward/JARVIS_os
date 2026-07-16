from fastapi.testclient import TestClient

from app.main import app
from app.market_intelligence.service import market_intelligence_service

client = TestClient(app)


def setup_function() -> None:
    market_intelligence_service.reset()


def test_trending_market_snapshot_and_watchlist() -> None:
    payload = {
        "symbol": "XAUUSD",
        "asset_class": "commodity",
        "priority": 1,
        "spread_score": 0.9,
        "session_liquidity": 0.85,
        "timeframes": [
            {"timeframe": "H4", "direction": "bullish", "structure_score": 0.85, "liquidity_score": 0.8, "volatility_score": 0.55},
            {"timeframe": "H1", "direction": "bullish", "structure_score": 0.8, "liquidity_score": 0.75, "volatility_score": 0.5},
            {"timeframe": "M15", "direction": "bullish", "structure_score": 0.7, "liquidity_score": 0.8, "volatility_score": 0.5},
        ],
    }
    created = client.post("/v1/market-intelligence/snapshots", json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["regime"] == "trending"
    assert body["bias"] == "bullish"
    assert body["confidence"] > 0.7

    watchlist = client.get("/v1/market-intelligence/watchlist").json()
    assert watchlist[0]["symbol"] == "XAUUSD"


def test_macro_event_increases_risk_without_execution() -> None:
    response = client.post(
        "/v1/market-intelligence/snapshots",
        json={
            "symbol": "NAS100",
            "asset_class": "index",
            "priority": 1,
            "timeframes": [{"timeframe": "H1", "direction": "neutral", "volatility_score": 0.8}],
            "macro_events": [{
                "title": "FOMC",
                "impact": 1.0,
                "affected_symbols": ["NAS100"],
                "scheduled_at": "2026-07-16T18:00:00Z"
            }]
        },
    )
    body = response.json()
    assert body["regime"] == "volatile"
    assert body["risk_score"] >= 0.65
    assert body["automatic_order_execution"] is False


def test_status_safety_flags() -> None:
    status = client.get("/v1/market-intelligence/status").json()
    assert status["automatic_order_execution"] is False
    assert status["automatic_merge"] is False
