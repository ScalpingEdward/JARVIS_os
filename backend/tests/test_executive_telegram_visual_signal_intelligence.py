import pytest

from app.executive_telegram_visual_signal_intelligence.models import (
    ChartAnnotation,
    TradeDirection,
    VisualSignalAssessmentCreate,
    VisualSignalState,
)
from app.executive_telegram_visual_signal_intelligence.service import ExecutiveTelegramVisualSignalIntelligenceService


def payload(**overrides):
    data = {
        "workspace_id": "ws-1",
        "source_key": "telegram:chat-1:message-1",
        "actor_id": "telegram-parser",
        "telegram_chat_id": "chat-1",
        "telegram_message_id": "message-1",
        "image_reference": "telegram://chat-1/message-1/chart.jpg",
        "image_sha256": "a" * 64,
        "image_quality_score": 90,
        "ocr_confidence": 88,
        "direction_confidence": 92,
        "structure_confidence": 90,
        "risk_brain_clear": True,
        "human_approved": True,
        "annotation": ChartAnnotation(
            symbol="XAUUSD",
            timeframe="M15",
            direction=TradeDirection.long,
            entry_low=2390.0,
            entry_high=2392.0,
            stop_loss=2384.0,
            take_profits=[2400.0, 2408.0],
            ict_concepts=["liquidity-sweep", "bullish-fvg", "market-structure-shift"],
            liquidity_levels=[2388.0, 2408.0],
            fair_value_gaps=["M15 bullish FVG 2390-2392"],
            market_structure_notes=["sell-side liquidity swept", "bullish displacement"],
            extracted_text=["LONG", "SL 2384", "TP 2400"],
        ),
    }
    data.update(overrides)
    return VisualSignalAssessmentCreate(**data)


def test_actionable_chart_signal_is_normalized_for_strategy_review():
    service = ExecutiveTelegramVisualSignalIntelligenceService()
    result = service.create(payload())

    assert result.state == VisualSignalState.actionable
    assert result.usable_for_strategy_review is True
    assert result.executable is False
    assert result.normalized_signal.symbol == "XAUUSD"
    assert result.scores.risk_completeness == 100


def test_human_approval_is_required():
    service = ExecutiveTelegramVisualSignalIntelligenceService()
    result = service.create(payload(human_approved=False))

    assert result.state == VisualSignalState.actionable
    assert result.usable_for_strategy_review is False
    assert "Human approval" in result.reasons[-1]


def test_low_quality_or_unknown_direction_is_rejected():
    service = ExecutiveTelegramVisualSignalIntelligenceService()
    annotation = payload().annotation.model_copy(update={"direction": TradeDirection.unknown})
    result = service.create(payload(image_quality_score=40, annotation=annotation))

    assert result.state == VisualSignalState.rejected
    assert result.usable_for_strategy_review is False


def test_missing_context_routes_to_manual_review():
    service = ExecutiveTelegramVisualSignalIntelligenceService()
    annotation = payload().annotation.model_copy(update={"symbol": None})
    result = service.create(payload(annotation=annotation))

    assert result.state == VisualSignalState.manual_review


def test_incomplete_risk_levels_are_validated_but_not_actionable():
    service = ExecutiveTelegramVisualSignalIntelligenceService()
    annotation = payload().annotation.model_copy(update={"stop_loss": None})
    result = service.create(payload(annotation=annotation))

    assert result.state == VisualSignalState.validated
    assert result.scores.risk_completeness < 100


def test_risk_brain_blocks_signal():
    service = ExecutiveTelegramVisualSignalIntelligenceService()
    result = service.create(payload(risk_brain_clear=False))

    assert result.state == VisualSignalState.rejected


def test_duplicate_source_and_image_are_blocked():
    service = ExecutiveTelegramVisualSignalIntelligenceService()
    service.create(payload())

    with pytest.raises(ValueError, match="Duplicate visual signal source key"):
        service.create(payload())

    with pytest.raises(ValueError, match="Duplicate chart image"):
        service.create(payload(source_key="telegram:chat-1:message-2"))


def test_workspace_isolation_and_audit():
    service = ExecutiveTelegramVisualSignalIntelligenceService()
    first = service.create(payload())
    second = service.create(
        payload(
            workspace_id="ws-2",
            source_key="telegram:chat-2:message-2",
            telegram_chat_id="chat-2",
            telegram_message_id="message-2",
            image_sha256="b" * 64,
        )
    )

    assert service.get(first.id, "ws-2") is None
    assert service.get(second.id, "ws-2") == second
    assert len(service.list_assessments("ws-1")) == 1
    assert len(service.audit("ws-2")) == 1
