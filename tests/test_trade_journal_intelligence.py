import pytest

from backend.app.modules.trade_journal_intelligence.models import (
    JournalAction,
    JournalCommand,
    JournalState,
    TradeJournalCreate,
    TradeOutcome,
)
from backend.app.modules.trade_journal_intelligence.service import (
    JournalError,
    TradeJournalIntelligenceService,
)


def payload(**overrides):
    data = {
        "workspace_id": "alpha",
        "source_key": "trade-001",
        "exposure_record_id": "exp-001",
        "position_record_id": "pos-001",
        "symbol": "xauusd",
        "direction": "long",
        "setup_grade": "A+",
        "confidence_score": 92,
        "planned_risk_percent": 0.5,
        "realized_r_multiple": 3.0,
        "holding_minutes": 45,
        "session": "london-new-york-overlap",
        "strategy_tags": ["liquidity-sweep", "fvg"],
        "followed_plan": True,
        "stop_respected": True,
        "target_plan_respected": True,
        "upstream_evidence_verified": True,
    }
    data.update(overrides)
    return TradeJournalCreate(**data)


def test_clean_trade_is_analyzed():
    service = TradeJournalIntelligenceService()
    record = service.create(payload())
    assert record.state == JournalState.ANALYZED
    assert record.analytics.outcome == TradeOutcome.WIN
    assert record.analytics.discipline_score == 100
    assert record.analytics.process_flags == []


def test_process_breach_requires_human_review():
    service = TradeJournalIntelligenceService()
    record = service.create(payload(followed_plan=False, stop_respected=False))
    assert record.state == JournalState.HUMAN_REVIEW_REQUIRED
    assert "plan-deviation" in record.analytics.process_flags
    assert "stop-discipline-breach" in record.analytics.process_flags


def test_evidence_and_risk_brain_gates_fail_closed():
    service = TradeJournalIntelligenceService()
    missing = service.create(payload(source_key="missing", upstream_evidence_verified=False))
    blocked = service.create(payload(source_key="blocked", risk_brain_blocked=True))
    assert missing.state == JournalState.EVIDENCE_REQUIRED
    assert blocked.state == JournalState.BLOCKED


def test_approval_and_issue_require_unique_tokens():
    service = TradeJournalIntelligenceService()
    first = service.create(payload())
    approved = service.act(
        "alpha",
        first.id,
        JournalAction(command=JournalCommand.APPROVE, actor="reviewer", approval_token="approve-1"),
    )
    assert approved.state == JournalState.APPROVED
    issued = service.act(
        "alpha",
        first.id,
        JournalAction(command=JournalCommand.ISSUE, actor="reviewer", downstream_receipt="receipt-1"),
    )
    assert issued.state == JournalState.ISSUED

    second = service.create(payload(source_key="trade-002"))
    with pytest.raises(JournalError, match="replay"):
        service.act(
            "alpha",
            second.id,
            JournalAction(command=JournalCommand.APPROVE, actor="reviewer", approval_token="approve-1"),
        )


def test_duplicate_source_and_workspace_isolation():
    service = TradeJournalIntelligenceService()
    record = service.create(payload())
    with pytest.raises(JournalError, match="duplicate"):
        service.create(payload())
    with pytest.raises(JournalError, match="not found"):
        service.get("other-workspace", record.id)


def test_summary_calculates_win_rate_and_expectancy():
    service = TradeJournalIntelligenceService()
    service.create(payload())
    service.create(payload(source_key="trade-002", realized_r_multiple=-1.0))
    summary = service.summary("alpha")
    assert summary["trades"] == 2
    assert summary["win_rate"] == 50.0
    assert summary["average_r"] == 1.0
    assert summary["expectancy_r"] == 1.0
