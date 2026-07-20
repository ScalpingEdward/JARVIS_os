import pytest

from app.executive_live_strategy_performance_lifecycle.models import (
    LifecyclePolicy,
    LifecycleState,
    StrategyLifecycleAssessmentCreate,
    StrategyPerformanceInput,
)
from app.executive_live_strategy_performance_lifecycle.service import (
    ExecutiveLiveStrategyPerformanceLifecycleService,
)


def strategy(**overrides):
    data = dict(
        strategy_id="ict-xau",
        broker_id="broker-a",
        symbol="XAUUSD",
        market_regime="trend",
        allocated_capital=10000,
        gross_pnl=1200,
        trading_costs=100,
        benchmark_pnl=200,
        max_drawdown_share=0.04,
        risk_share=0.20,
        win_rate=0.58,
        profit_factor=1.6,
        sample_trades=60,
        regime_fit_score=82,
        execution_quality_score=88,
    )
    data.update(overrides)
    return StrategyPerformanceInput(**data)


def payload(**overrides):
    data = dict(
        workspace_id="ws-1",
        source_key="lifecycle-1",
        actor_id="master-brano",
        human_approved=True,
        risk_brain_clear=True,
        consecutive_failed_reviews=0,
        strategy=strategy(),
        policy=LifecyclePolicy(),
    )
    data.update(overrides)
    return StrategyLifecycleAssessmentCreate(**data)


def test_positive_alpha_promotes_strategy():
    service = ExecutiveLiveStrategyPerformanceLifecycleService()
    result = service.create(payload())
    assert result.state == LifecycleState.promote
    assert result.attribution.alpha_return_share > 0
    assert result.deployable is True


def test_small_sample_observes_strategy():
    service = ExecutiveLiveStrategyPerformanceLifecycleService()
    result = service.create(payload(strategy=strategy(sample_trades=10)))
    assert result.state == LifecycleState.observe
    assert result.deployable is False


def test_drawdown_pauses_strategy():
    service = ExecutiveLiveStrategyPerformanceLifecycleService()
    result = service.create(payload(strategy=strategy(max_drawdown_share=0.15)))
    assert result.state == LifecycleState.pause
    assert result.recommended_action == "pause"


def test_repeated_failures_retire_strategy():
    service = ExecutiveLiveStrategyPerformanceLifecycleService()
    result = service.create(payload(consecutive_failed_reviews=3))
    assert result.state == LifecycleState.retire


def test_risk_brain_blocks_action():
    service = ExecutiveLiveStrategyPerformanceLifecycleService()
    result = service.create(payload(risk_brain_clear=False))
    assert result.state == LifecycleState.blocked
    assert result.deployable is False


def test_human_approval_gates_lifecycle_action():
    service = ExecutiveLiveStrategyPerformanceLifecycleService()
    result = service.create(payload(human_approved=False))
    assert result.state == LifecycleState.promote
    assert result.deployable is False


def test_workspace_isolation_and_duplicate_protection():
    service = ExecutiveLiveStrategyPerformanceLifecycleService()
    created = service.create(payload())
    assert service.get(created.id, "other") is None
    with pytest.raises(ValueError):
        service.create(payload())
