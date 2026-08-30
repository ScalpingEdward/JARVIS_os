"""Tests for strategies API and service layer."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.strategies.models import (
    FairValueGap,
    HTFBias,
    MarketSnapshot,
    OrderBlock,
    OrderBlockType,
)

client = TestClient(app)


def _valid_long_snapshot() -> dict:
    """Create a valid long setup snapshot as JSON."""
    return {
        "symbol": "EURUSD",
        "current_price": 1.10000,
        "bid": 1.09995,
        "ask": 1.10005,
        "spread": 0.00010,
        "htf_bias": "bullish",
        "session": "london",
        "order_blocks": [
            {
                "type": "bullish",
                "high": 1.10010,
                "low": 1.09990,
                "open": 1.09990,
                "close": 1.10000,
            }
        ],
        "fvgs": [{"side": "bullish", "top": 1.10200, "bottom": 1.09980}],
        "structure_levels": [],
    }


def _valid_short_snapshot() -> dict:
    """Create a valid short setup snapshot as JSON."""
    return {
        "symbol": "GBPUSD",
        "current_price": 1.25000,
        "bid": 1.24995,
        "ask": 1.25005,
        "spread": 0.00010,
        "htf_bias": "bearish",
        "session": "ny",
        "order_blocks": [
            {
                "type": "bearish",
                "high": 1.25010,
                "low": 1.24990,
                "open": 1.25010,
                "close": 1.25000,
            }
        ],
        "fvgs": [{"side": "bearish", "top": 1.25020, "bottom": 1.24800}],
        "structure_levels": [],
    }


def _no_setup_snapshot() -> dict:
    """Create a snapshot that produces no setup."""
    return {
        "symbol": "EURUSD",
        "current_price": 1.10000,
        "bid": 1.09995,
        "ask": 1.10005,
        "spread": 0.00010,
        "htf_bias": "neutral",
        "session": "asian",
        "order_blocks": [],
        "fvgs": [],
        "structure_levels": [],
    }


# -- list strategies ---------------------------------------------------------


def test_list_strategies() -> None:
    """GET /v1/strategies returns all available strategies."""
    resp = client.get("/v1/strategies/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1  # At least scalping_3tp
    # Check scalping_3tp is present
    scalping = next((s for s in data if s["id"] == "scalping_3tp"), None)
    assert scalping is not None
    assert scalping["name"] == "Scalping 3TP (FVG + Order Block)"
    assert "FVG" in scalping["description"]


# -- evaluate single strategy ------------------------------------------------


def test_evaluate_strategy_valid_long() -> None:
    """POST /v1/strategies/evaluate/{strategy_id} with valid long setup."""
    snapshot = _valid_long_snapshot()
    resp = client.post("/v1/strategies/evaluate/scalping_3tp", json=snapshot)
    assert resp.status_code == 200
    data = resp.json()
    assert data["strategy_id"] == "scalping_3tp"
    assert data["symbol"] == "EURUSD"
    assert data["setup"] is not None
    setup = data["setup"]
    assert setup["side"] == "buy"
    assert setup["entry_price"] == snapshot["ask"]
    assert setup["stop_loss"] < snapshot["ask"]
    assert setup["risk_reward"] >= 2.0
    assert len(setup["take_profits"]) == 3


def test_evaluate_strategy_valid_short() -> None:
    """POST /v1/strategies/evaluate/{strategy_id} with valid short setup."""
    snapshot = _valid_short_snapshot()
    resp = client.post("/v1/strategies/evaluate/scalping_3tp", json=snapshot)
    assert resp.status_code == 200
    data = resp.json()
    assert data["setup"] is not None
    setup = data["setup"]
    assert setup["side"] == "sell"
    assert setup["entry_price"] == snapshot["bid"]
    assert setup["stop_loss"] > snapshot["bid"]


def test_evaluate_strategy_no_setup() -> None:
    """POST /v1/strategies/evaluate/{strategy_id} with no valid setup."""
    snapshot = _no_setup_snapshot()
    resp = client.post("/v1/strategies/evaluate/scalping_3tp", json=snapshot)
    assert resp.status_code == 200
    data = resp.json()
    assert data["setup"] is None
    assert data["no_setup_reason"] is not None
    assert len(data["no_setup_reason"]) > 0


def test_evaluate_strategy_unknown_strategy() -> None:
    """POST /v1/strategies/evaluate/{strategy_id} with unknown strategy."""
    snapshot = _valid_long_snapshot()
    resp = client.post("/v1/strategies/evaluate/nonexistent", json=snapshot)
    assert resp.status_code == 404
    assert "Unknown strategy" in resp.json()["detail"]


def test_evaluate_strategy_invalid_snapshot() -> None:
    """POST /v1/strategies/evaluate/{strategy_id} with invalid snapshot."""
    invalid = {"symbol": "EURUSD"}  # Missing required fields
    resp = client.post("/v1/strategies/evaluate/scalping_3tp", json=invalid)
    assert resp.status_code == 422  # Validation error


# -- evaluate all strategies -------------------------------------------------


def test_evaluate_all_strategies() -> None:
    """POST /v1/strategies/evaluate-all evaluates all registered strategies."""
    snapshot = _valid_long_snapshot()
    resp = client.post("/v1/strategies/evaluate-all", json=snapshot)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1  # At least scalping_3tp
    # Check scalping_3tp result
    scalping_result = next((r for r in data if r["strategy_id"] == "scalping_3tp"), None)
    assert scalping_result is not None
    assert scalping_result["setup"] is not None


def test_evaluate_all_includes_no_setups() -> None:
    """evaluate-all includes results even if no setup was found."""
    snapshot = _no_setup_snapshot()
    resp = client.post("/v1/strategies/evaluate-all", json=snapshot)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    # All results should have no setup
    for result in data:
        assert result["setup"] is None
        assert result["no_setup_reason"] is not None


# -- find setups -------------------------------------------------------------


def test_find_setups_returns_only_valid() -> None:
    """POST /v1/strategies/find-setups returns only strategies with setups."""
    snapshot = _valid_long_snapshot()
    resp = client.post("/v1/strategies/find-setups", json=snapshot)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # All returned results must have a setup
    for result in data:
        assert result["setup"] is not None
        assert result["no_setup_reason"] is None


def test_find_setups_empty_when_no_setups() -> None:
    """find-setups returns empty list when no strategies find setups."""
    snapshot = _no_setup_snapshot()
    resp = client.post("/v1/strategies/find-setups", json=snapshot)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_find_setups_multiple_strategies() -> None:
    """find-setups can return multiple setups if multiple strategies match."""
    # For now only scalping_3tp exists, so max 1 result
    # When we add ict/smc/open_range, this test becomes more interesting
    snapshot = _valid_long_snapshot()
    resp = client.post("/v1/strategies/find-setups", json=snapshot)
    assert resp.status_code == 200
    data = resp.json()
    # Currently only scalping_3tp
    assert len(data) == 1
    assert data[0]["strategy_id"] == "scalping_3tp"


# -- service layer tests (unit) ----------------------------------------------


def test_service_list_strategies() -> None:
    """StrategyService.list_strategies returns metadata."""
    from app.strategies.service import strategy_service

    strategies = strategy_service.list_strategies()
    assert len(strategies) >= 1
    assert any(s["id"] == "scalping_3tp" for s in strategies)


def test_service_evaluate_strategy() -> None:
    """StrategyService.evaluate_strategy calls the correct strategy."""
    from app.strategies.service import strategy_service

    snapshot = MarketSnapshot(
        symbol="EURUSD",
        current_price=1.10000,
        bid=1.09995,
        ask=1.10005,
        spread=0.00010,
        htf_bias=HTFBias.bullish,
        order_blocks=[
            OrderBlock(
                type=OrderBlockType.bullish,
                high=1.10010,
                low=1.09990,
                open=1.09990,
                close=1.10000,
            )
        ],
        fvgs=[FairValueGap(side="bullish", top=1.10200, bottom=1.09980)],
    )
    result = strategy_service.evaluate_strategy("scalping_3tp", snapshot)
    assert result.strategy_id == "scalping_3tp"
    assert result.setup is not None


def test_service_evaluate_unknown_strategy() -> None:
    """StrategyService.evaluate_strategy raises on unknown strategy."""
    from app.strategies.service import StrategyServiceError, strategy_service

    snapshot = MarketSnapshot(
        symbol="EURUSD",
        current_price=1.10000,
        bid=1.09995,
        ask=1.10005,
        spread=0.00010,
    )
    with pytest.raises(StrategyServiceError, match="Unknown strategy"):
        strategy_service.evaluate_strategy("nonexistent", snapshot)


def test_service_evaluate_all() -> None:
    """StrategyService.evaluate_all evaluates all strategies."""
    from app.strategies.service import strategy_service

    snapshot = MarketSnapshot(
        symbol="EURUSD",
        current_price=1.10000,
        bid=1.09995,
        ask=1.10005,
        spread=0.00010,
        htf_bias=HTFBias.neutral,
    )
    results = strategy_service.evaluate_all(snapshot)
    assert len(results) >= 1
    assert all(r.strategy_id in ["scalping_3tp"] for r in results)


def test_service_find_setups() -> None:
    """StrategyService.find_setups filters to only setups."""
    from app.strategies.service import strategy_service

    snapshot_with = MarketSnapshot(
        symbol="EURUSD",
        current_price=1.10000,
        bid=1.09995,
        ask=1.10005,
        spread=0.00010,
        htf_bias=HTFBias.bullish,
        order_blocks=[
            OrderBlock(
                type=OrderBlockType.bullish,
                high=1.10010,
                low=1.09990,
                open=1.09990,
                close=1.10000,
            )
        ],
        fvgs=[FairValueGap(side="bullish", top=1.10200, bottom=1.09980)],
    )
    results_with = strategy_service.find_setups(snapshot_with)
    assert len(results_with) >= 1
    assert all(r.setup is not None for r in results_with)

    snapshot_without = MarketSnapshot(
        symbol="EURUSD",
        current_price=1.10000,
        bid=1.09995,
        ask=1.10005,
        spread=0.00010,
        htf_bias=HTFBias.neutral,
    )
    results_without = strategy_service.find_setups(snapshot_without)
    assert len(results_without) == 0
