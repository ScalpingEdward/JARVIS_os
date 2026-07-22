from datetime import datetime, timedelta, timezone

import pytest

from app.modules.market_structure_analyzer.models import (
    ImbalanceZone,
    MarketBias,
    MarketStructureCreate,
    StructureAction,
    StructureCommand,
    StructureState,
    SwingPoint,
)
from app.modules.market_structure_analyzer.service import MarketStructureAnalyzerService, MarketStructureError


def payload(**overrides) -> MarketStructureCreate:
    now = datetime.now(timezone.utc)
    data = {
        "workspace_id": "desk-a",
        "source_key": "xau-h1-structure-1",
        "symbol": "XAUUSD",
        "timeframe": "15m",
        "higher_timeframe": "1h",
        "current_price": 2412.0,
        "swings": [
            SwingPoint(timestamp=now - timedelta(minutes=60), price=2390, kind="low"),
            SwingPoint(timestamp=now - timedelta(minutes=45), price=2410, kind="high"),
            SwingPoint(timestamp=now - timedelta(minutes=30), price=2400, kind="low"),
            SwingPoint(timestamp=now - timedelta(minutes=15), price=2420, kind="high"),
        ],
        "zones": [
            ImbalanceZone(kind="fvg", low=2405, high=2409, timeframe="15m"),
            ImbalanceZone(kind="liquidity", low=2428, high=2430, timeframe="1h"),
            ImbalanceZone(kind="liquidity", low=2384, high=2386, timeframe="1h"),
        ],
        "liquidity_sweep": True,
        "displacement_confirmed": True,
        "bos_confirmed": True,
        "choch_confirmed": False,
        "session_alignment": True,
        "evidence_refs": ["chart://xau-h1", "feed://broker-1"],
    }
    data.update(overrides)
    return MarketStructureCreate(**data)


def test_detects_bullish_structure_and_confluence() -> None:
    service = MarketStructureAnalyzerService()
    record = service.create(payload())
    assert record.bias == MarketBias.BULLISH
    assert record.state == StructureState.STRUCTURE_READY
    assert record.confluence_score >= 65
    assert record.nearest_liquidity_above == 2428
    assert record.nearest_liquidity_below == 2386


def test_news_risk_forces_human_review() -> None:
    service = MarketStructureAnalyzerService()
    record = service.create(payload(news_risk_active=True))
    assert record.state == StructureState.HUMAN_REVIEW_REQUIRED
    assert any("news risk" in finding.lower() for finding in record.findings)


def test_missing_evidence_and_risk_block_fail_closed() -> None:
    service = MarketStructureAnalyzerService()
    missing = service.create(payload(source_key="missing", evidence_refs=[]))
    blocked = service.create(payload(source_key="blocked", risk_brain_hard_block=True))
    assert missing.state == StructureState.EVIDENCE_REQUIRED
    assert blocked.state == StructureState.BLOCKED


def test_approval_issue_and_replay_protection() -> None:
    service = MarketStructureAnalyzerService()
    first = service.create(payload())
    second = service.create(payload(source_key="xau-h1-structure-2"))

    service.execute(
        "desk-a",
        first.id,
        StructureAction(command=StructureCommand.APPROVE, actor="brano", approval_token="approve-1"),
    )
    issued = service.execute(
        "desk-a",
        first.id,
        StructureAction(command=StructureCommand.ISSUE, actor="brano", downstream_receipt="visualizer-1"),
    )
    assert issued.state == StructureState.ISSUED_TO_VISUALIZER

    with pytest.raises(MarketStructureError, match="approval token replay"):
        service.execute(
            "desk-a",
            second.id,
            StructureAction(command=StructureCommand.APPROVE, actor="brano", approval_token="approve-1"),
        )


def test_duplicate_and_workspace_isolation() -> None:
    service = MarketStructureAnalyzerService()
    record = service.create(payload())
    with pytest.raises(MarketStructureError, match="duplicate source_key"):
        service.create(payload())
    with pytest.raises(MarketStructureError, match="record not found"):
        service.get("desk-b", record.id)


def test_requires_two_highs_and_two_lows() -> None:
    request = payload()
    request.swings = request.swings[:3] + [
        SwingPoint(
            timestamp=request.swings[-1].timestamp,
            price=2415,
            kind="low",
        )
    ]
    service = MarketStructureAnalyzerService()
    with pytest.raises(MarketStructureError, match="two swing highs"):
        service.create(request)
