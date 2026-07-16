from fastapi.testclient import TestClient

from app.main import app
from app.market_vision.service import market_vision_service


client = TestClient(app)


def setup_function() -> None:
    market_vision_service.reset()


def test_combines_multiple_timeframes_and_structured_biases() -> None:
    payload = {
        "symbol": "XAUUSD",
        "market_bias": "bullish",
        "market_confidence": 0.8,
        "orderflow_bias": "bullish",
        "orderflow_confidence": 0.75,
        "current_price": 2401.2,
        "observations": [
            {
                "source": "tradingview",
                "image_ref": "chart-h4.png",
                "timeframe": "H4",
                "image_quality": 0.9,
                "detected_symbol": "XAUUSD",
                "detected_bias": "bullish",
                "regions": [
                    {
                        "kind": "liquidity_sweep",
                        "label": "sell-side liquidity sweep",
                        "price_low": 2390,
                        "price_high": 2392,
                        "direction": "bullish",
                        "confidence": 0.8
                    }
                ]
            },
            {
                "source": "mt5",
                "image_ref": "chart-m15.png",
                "timeframe": "M15",
                "image_quality": 0.85,
                "detected_symbol": "XAUUSD",
                "detected_bias": "bullish",
                "regions": [
                    {
                        "kind": "bos",
                        "label": "bullish break of structure",
                        "direction": "bullish",
                        "confidence": 0.82
                    }
                ]
            }
        ]
    }
    response = client.post("/v1/market-vision/analyses", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["visual_bias"] == "bullish"
    assert body["multi_timeframe_alignment"] == 1
    assert body["structured_data_alignment"] > 0.7
    assert body["confidence"] > 0.7
    assert len(body["confirmations"]) == 2


def test_flags_symbol_mismatch_low_quality_and_single_timeframe() -> None:
    response = client.post(
        "/v1/market-vision/analyses",
        json={
            "symbol": "XAUUSD",
            "observations": [
                {
                    "source": "other",
                    "image_ref": "unclear.png",
                    "timeframe": "M5",
                    "image_quality": 0.3,
                    "detected_symbol": "BTCUSD",
                    "detected_bias": "insufficient_data"
                }
            ]
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["visual_bias"] == "insufficient_data"
    assert body["uncertainty"] > 0.5
    assert any("different symbol" in item for item in body["warnings"])
    assert any("low visual quality" in item for item in body["warnings"])
    assert any("only one timeframe" in item for item in body["warnings"])


def test_market_vision_safety_flags_remain_disabled() -> None:
    payload = client.get("/v1/market-vision/status").json()
    assert payload["automatic_order_execution"] is False
    assert payload["automatic_merge"] is False
