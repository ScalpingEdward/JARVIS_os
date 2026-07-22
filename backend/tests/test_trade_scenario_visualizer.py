from datetime import datetime, timezone

import pytest

from app.modules.trade_scenario_visualizer.models import (
    PriceZone,
    ScenarioAction,
    ScenarioCommand,
    ScenarioDirection,
    ScenarioPoint,
    ScenarioState,
    TradeScenarioCreate,
)
from app.modules.trade_scenario_visualizer.service import (
    TradeScenarioError,
    TradeScenarioVisualizerService,
)


def payload(**overrides):
    values = {
        "workspace_id": "desk-a",
        "source_key": "xau-h1-001",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "direction": ScenarioDirection.LONG,
        "thesis": "Liquidity sweep followed by bullish displacement into an imbalance.",
        "entry_price": 2400.0,
        "stop_price": 2390.0,
        "target_prices": [2420.0, 2430.0],
        "confidence_score": 82,
        "risk_reward_minimum": 1.5,
        "setup_evidence": {"bos": True, "fvg": True},
        "zones": [PriceZone(label="H1 FVG", low=2398, high=2403, kind="fvg")],
        "points": [
            ScenarioPoint(
                timestamp=datetime.now(timezone.utc),
                price=2396,
                label="Liquidity sweep",
                kind="liquidity",
            )
        ],
    }
    values.update(overrides)
    return TradeScenarioCreate(**values)


def test_builds_long_chart_payload_and_rr():
    service = TradeScenarioVisualizerService()
    record = service.create(payload())
    assert record.state == ScenarioState.READY
    assert record.risk_reward_ratios == [2.0, 3.0]
    assert record.tradingview_payload["execution_enabled"] is False
    assert any(item.label == "Entry" for item in record.annotations)
    assert any(item.label == "H1 FVG" for item in record.annotations)


def test_low_rr_requires_human_review():
    service = TradeScenarioVisualizerService()
    record = service.create(payload(target_prices=[2405.0]))
    assert record.state == ScenarioState.HUMAN_REVIEW_REQUIRED


def test_risk_brain_block_is_authoritative():
    service = TradeScenarioVisualizerService()
    record = service.create(payload(risk_brain_hard_block=True))
    assert record.state == ScenarioState.BLOCKED


def test_evidence_is_required():
    service = TradeScenarioVisualizerService()
    record = service.create(payload(setup_evidence={}))
    assert record.state == ScenarioState.EVIDENCE_REQUIRED


def test_approval_and_publish_are_replay_protected():
    service = TradeScenarioVisualizerService()
    first = service.create(payload())
    service.execute(
        "desk-a",
        first.id,
        ScenarioAction(command=ScenarioCommand.APPROVE, actor="brano", review_token="review-1"),
    )
    published = service.execute(
        "desk-a",
        first.id,
        ScenarioAction(command=ScenarioCommand.PUBLISH, actor="brano", publish_receipt="pub-1"),
    )
    assert published.state == ScenarioState.PUBLISHED

    second = service.create(payload(source_key="xau-h1-002"))
    with pytest.raises(TradeScenarioError, match="review token replay"):
        service.execute(
            "desk-a",
            second.id,
            ScenarioAction(command=ScenarioCommand.APPROVE, actor="brano", review_token="review-1"),
        )


def test_duplicate_source_and_workspace_isolation():
    service = TradeScenarioVisualizerService()
    record = service.create(payload())
    with pytest.raises(TradeScenarioError, match="duplicate source_key"):
        service.create(payload())
    with pytest.raises(TradeScenarioError, match="record not found"):
        service.get("desk-b", record.id)


def test_invalid_long_geometry_is_rejected():
    with pytest.raises(ValueError, match="long stop"):
        payload(stop_price=2410.0)
