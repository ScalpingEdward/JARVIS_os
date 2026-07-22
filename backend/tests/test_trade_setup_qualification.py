import pytest

from app.modules.trade_setup_qualification.models import (
    ConfirmationSignal,
    SetupAction,
    SetupCommand,
    SetupState,
    TradeSetupCreate,
)
from app.modules.trade_setup_qualification.service import (
    TradeSetupError,
    TradeSetupQualificationService,
)


def payload(**overrides) -> TradeSetupCreate:
    data = {
        "workspace_id": "desk-a",
        "source_key": "xau-m15-001",
        "market_structure_record_id": "structure-1",
        "v21_14_approved": True,
        "v21_14_evidence": {"state": "approved", "bias": "bullish"},
        "symbol": "XAUUSD",
        "timeframe": "15m",
        "direction": "long",
        "entry_price": 2400.0,
        "stop_price": 2390.0,
        "target_prices": [2420.0, 2430.0],
        "confidence_score": 86,
        "minimum_rr": 1.5,
        "minimum_confirmation_score": 70,
        "spread_points": 25,
        "maximum_spread_points": 50,
        "confirmations": [
            ConfirmationSignal(key="bos", category="structure", present=True, weight=3, evidence_ref="v21.14:bos"),
            ConfirmationSignal(key="sweep", category="liquidity", present=True, weight=2, evidence_ref="v21.14:sweep"),
            ConfirmationSignal(key="fvg", category="imbalance", present=True, weight=2, evidence_ref="chart:fvg"),
            ConfirmationSignal(key="session", category="session", present=True, weight=1, evidence_ref="session:london"),
        ],
    }
    data.update(overrides)
    return TradeSetupCreate(**data)


def test_qualifies_high_confluence_setup() -> None:
    service = TradeSetupQualificationService()
    record = service.create(payload())
    assert record.state == SetupState.QUALIFIED
    assert record.qualification.confirmation_score == 100
    assert record.qualification.risk_reward_ratios == [2.0, 3.0]
    assert record.qualification.setup_grade == "A+"


def test_news_risk_forces_human_review() -> None:
    service = TradeSetupQualificationService()
    record = service.create(payload(active_news_risk=True))
    assert record.state == SetupState.HUMAN_REVIEW_REQUIRED


def test_spread_and_session_fail_closed() -> None:
    service = TradeSetupQualificationService()
    spread = service.create(payload(source_key="spread", spread_points=80))
    session = service.create(payload(source_key="session", session_allowed=False))
    assert spread.state == SetupState.BLOCKED
    assert session.state == SetupState.BLOCKED


def test_missing_upstream_evidence_and_risk_block() -> None:
    service = TradeSetupQualificationService()
    missing = service.create(payload(source_key="missing", v21_14_evidence={}))
    blocked = service.create(payload(source_key="blocked", risk_brain_hard_block=True))
    assert missing.state == SetupState.EVIDENCE_REQUIRED
    assert blocked.state == SetupState.BLOCKED


def test_approval_issue_and_replay_protection() -> None:
    service = TradeSetupQualificationService()
    first = service.create(payload(source_key="first"))
    service.execute(
        "desk-a",
        first.id,
        SetupAction(command=SetupCommand.APPROVE, actor="brano", approval_token="approval-1"),
    )
    issued = service.execute(
        "desk-a",
        first.id,
        SetupAction(command=SetupCommand.ISSUE, actor="brano", downstream_receipt="visualizer-1"),
    )
    assert issued.state == SetupState.ISSUED_TO_VISUALIZER

    second = service.create(payload(source_key="second"))
    with pytest.raises(TradeSetupError, match="approval token replay"):
        service.execute(
            "desk-a",
            second.id,
            SetupAction(command=SetupCommand.APPROVE, actor="brano", approval_token="approval-1"),
        )


def test_duplicate_source_and_workspace_isolation() -> None:
    service = TradeSetupQualificationService()
    record = service.create(payload())
    with pytest.raises(TradeSetupError, match="duplicate source_key"):
        service.create(payload())
    with pytest.raises(TradeSetupError, match="record not found"):
        service.get("desk-b", record.id)


def test_invalid_long_geometry_is_rejected() -> None:
    with pytest.raises(ValueError, match="long stop"):
        payload(stop_price=2410.0)
