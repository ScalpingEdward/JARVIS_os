from datetime import datetime, timedelta, timezone

from app.executive_institutional_trade_journal.models import (
    InstitutionalTradeJournalCreate,
    TradeDecisionEvidence,
    TradeJournalExecuteRequest,
    TradeJournalState,
)
from app.executive_institutional_trade_journal.service import InstitutionalTradeJournalService


def trade(**overrides) -> TradeDecisionEvidence:
    opened = datetime.now(timezone.utc) - timedelta(minutes=10)
    data = dict(
        trade_id="t-1", strategy_id="ict-gold", account_id="a-1", symbol="XAUUSD", side="buy",
        setup_name="liquidity-sweep-fvg", entry_price=2400, stop_loss=2395, take_profit=2410, exit_price=2408,
        risk_amount=100, pnl=160, planned_rr=2, realized_rr=1.6, signal_confidence=82, market_score=85,
        market_regime="trend", session="new-york", entry_reason="sweep plus displacement and FVG",
        exit_reason="managed take profit", mae_r=0.25, mfe_r=1.8, slippage_bps=1, holding_seconds=600,
        routed_by_v19_06=True, market_allowed_by_v19_08=True, shadow_validated_by_v19_09=True,
        opened_at=opened, closed_at=opened + timedelta(minutes=10),
    )
    data.update(overrides)
    return TradeDecisionEvidence(**data)


def payload(**overrides) -> InstitutionalTradeJournalCreate:
    data = dict(
        workspace_id="w-1", source_key="journal-1", actor_id="tester",
        account_risk_approved=True, prop_rules_approved=True, trade=trade(),
    )
    data.update(overrides)
    return InstitutionalTradeJournalCreate(**data)


def test_upstream_evidence_is_mandatory():
    service = InstitutionalTradeJournalService()
    record = service.create(payload(trade=trade(market_allowed_by_v19_08=False)))
    assert record.state == TradeJournalState.EVIDENCE_REQUIRED


def test_good_process_creates_pending_journal_and_replay():
    service = InstitutionalTradeJournalService()
    record = service.create(payload())
    assert record.state == TradeJournalState.JOURNAL_PENDING
    assert record.process_score >= 75
    assert record.outcome_classification == "good-process-good-outcome"
    assert len(record.replay) == 5


def test_profitable_bad_process_still_requires_review():
    service = InstitutionalTradeJournalService()
    record = service.create(payload(trade=trade(signal_confidence=50, market_score=50, slippage_bps=12, mae_r=2.5, holding_seconds=1)))
    assert record.state == TradeJournalState.REVIEW_REQUIRED
    assert record.outcome_classification == "bad-process-good-outcome"


def test_human_approval_required_for_completion_and_lesson():
    service = InstitutionalTradeJournalService()
    record = service.create(payload())
    try:
        service.execute(record.id, "w-1", TradeJournalExecuteRequest(actor_id="tester", action="complete"))
        assert False
    except ValueError as exc:
        assert "human approval" in str(exc)
    completed = service.execute(record.id, "w-1", TradeJournalExecuteRequest(actor_id="tester", action="complete", human_approved=True))
    assert completed.state == TradeJournalState.JOURNAL_COMPLETE
    learned = service.execute(record.id, "w-1", TradeJournalExecuteRequest(actor_id="tester", action="approve-lesson", human_approved=True))
    assert learned.state == TradeJournalState.LESSON_APPROVED


def test_workspace_isolation_and_duplicate_protection():
    service = InstitutionalTradeJournalService()
    record = service.create(payload())
    assert service.get(record.id, "other") is None
    try:
        service.create(payload())
        assert False
    except ValueError as exc:
        assert "duplicate" in str(exc)
