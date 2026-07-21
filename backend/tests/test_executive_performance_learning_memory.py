from app.executive_performance_learning_memory.models import (
    PerformanceLearningCreate,
    PerformanceLearningExecuteRequest,
    PerformanceLearningState,
    TradeOutcome,
)
from app.executive_performance_learning_memory.service import PerformanceLearningMemoryService


def trade(index: int, pnl: float, realized_rr: float, confidence: float = 70) -> TradeOutcome:
    return TradeOutcome(
        trade_id=f"t-{index}", strategy_id="ict-gold", symbol="XAUUSD", account_id="a-1",
        pnl=pnl, risk_amount=100, planned_rr=2, realized_rr=realized_rr,
        holding_seconds=300, slippage_bps=1, regime="trend", signal_confidence=confidence,
        routed_by_v19_06=True,
    )


def payload(**overrides) -> PerformanceLearningCreate:
    data = dict(
        workspace_id="w-1", source_key="batch-1", actor_id="tester",
        min_sample_size=4, baseline_win_rate_pct=50, baseline_expectancy_r=0.5,
        outcomes=[
            trade(1, 200, 2, 80),
            trade(2, -100, -1, 20),
            trade(3, 200, 2, 80),
            trade(4, -100, -1, 20),
        ],
    )
    data.update(overrides)
    return PerformanceLearningCreate(**data)


def test_learning_requires_v1906_route_evidence():
    service = PerformanceLearningMemoryService()
    bad = payload(outcomes=[trade(1, 100, 1), trade(2, 100, 1), trade(3, 100, 1), trade(4, 100, 1)])
    bad.outcomes[0].routed_by_v19_06 = False
    record = service.create(bad)
    assert record.state == PerformanceLearningState.ROUTE_EVIDENCE_REQUIRED


def test_positive_sample_becomes_learning_pending():
    service = PerformanceLearningMemoryService()
    record = service.create(payload())
    assert record.state == PerformanceLearningState.LEARNING_PENDING
    assert record.portfolio_expectancy_r == 0.5
    assert record.strategies[0].trades == 4


def test_negative_expectancy_requires_pause_review():
    service = PerformanceLearningMemoryService()
    outcomes = [trade(i, -100, -1, 90) for i in range(1, 5)]
    record = service.create(payload(outcomes=outcomes))
    assert record.state == PerformanceLearningState.DEGRADATION_DETECTED
    assert record.recommendations[0].action == "pause"


def test_human_approval_required_before_memory_activation():
    service = PerformanceLearningMemoryService()
    record = service.create(payload())
    try:
        service.execute(record.id, "w-1", PerformanceLearningExecuteRequest(actor_id="tester", action="activate-memory"))
        assert False
    except ValueError as exc:
        assert "human approval" in str(exc)
    activated = service.execute(record.id, "w-1", PerformanceLearningExecuteRequest(actor_id="tester", action="activate-memory", human_approved=True))
    assert activated.state == PerformanceLearningState.MEMORY_ACTIVE


def test_workspace_isolation_and_duplicate_protection():
    service = PerformanceLearningMemoryService()
    record = service.create(payload())
    assert service.get(record.id, "other") is None
    try:
        service.create(payload())
        assert False
    except ValueError as exc:
        assert "duplicate" in str(exc)
