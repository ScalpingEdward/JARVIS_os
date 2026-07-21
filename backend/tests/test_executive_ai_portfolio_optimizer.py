import pytest

from app.executive_ai_portfolio_optimizer.models import (
    PortfolioOptimizerCreate,
    PortfolioOptimizerExecuteRequest,
    PortfolioOptimizerState,
    StrategyPerformanceInput,
    StressScenarioInput,
)
from app.executive_ai_portfolio_optimizer.service import AIPortfolioOptimizerService


def strategy(strategy_id: str, score_bias: float = 0) -> StrategyPerformanceInput:
    return StrategyPerformanceInput(
        strategy_id=strategy_id,
        strategy_type="ict",
        current_weight_pct=20,
        trades=120,
        win_rate_pct=58 + score_bias,
        expectancy_r=0.45 + score_bias / 100,
        profit_factor=1.8,
        sharpe=1.4,
        sortino=2.0,
        max_drawdown_pct=4,
        recovery_factor=2.5,
        ulcer_index=2,
        volatility_pct=8,
        correlation_to_portfolio=0.25,
        stability_score=82,
        shadow_validated_by_v19_09=True,
        journal_validated_by_v19_10=True,
    )


def payload(source_key: str = "opt-1", human_approved: bool = False) -> PortfolioOptimizerCreate:
    return PortfolioOptimizerCreate(
        workspace_id="alpha",
        source_key=source_key,
        actor_id="tester",
        account_equity=100000,
        daily_loss_limit_pct=4,
        max_drawdown_limit_pct=10,
        max_portfolio_heat_pct=8,
        max_strategy_weight_pct=45,
        cash_floor_pct=10,
        monte_carlo_runs=1000,
        account_risk_approved=True,
        prop_rules_approved=True,
        market_allowed_by_v19_08=True,
        human_approved=human_approved,
        strategies=[strategy("ict", 4), strategy("scalping", -2)],
        stress=StressScenarioInput(
            flash_crash_loss_pct=6,
            spread_explosion_loss_pct=2,
            liquidity_removal_loss_pct=4,
            server_delay_loss_pct=1,
            slippage_loss_pct=2,
        ),
    )


def test_valid_optimizer_requires_human_approval():
    service = AIPortfolioOptimizerService()
    record = service.create(payload())
    assert record.state == PortfolioOptimizerState.APPROVAL_REQUIRED
    assert len(record.recommendations) == 2
    assert record.recommended_cash_pct >= 10
    assert record.monte_carlo is not None
    assert record.stress_test is not None and record.stress_test.passed


def test_approved_recommendation_never_executes_live_change():
    service = AIPortfolioOptimizerService()
    record = service.create(payload(human_approved=True))
    assert record.state == PortfolioOptimizerState.RECOMMENDATION_READY
    approved = service.execute(
        record.id,
        "alpha",
        PortfolioOptimizerExecuteRequest(actor_id="owner", action="approve", human_approved=True),
    )
    assert approved.state == PortfolioOptimizerState.APPROVED
    assert "no live changes executed" in approved.detail


def test_missing_upstream_evidence_fails_closed():
    service = AIPortfolioOptimizerService()
    data = payload().model_copy(update={"market_allowed_by_v19_08": False})
    record = service.create(data)
    assert record.state == PortfolioOptimizerState.EVIDENCE_REQUIRED


def test_stress_breach_requires_review():
    service = AIPortfolioOptimizerService()
    data = payload().model_copy(update={
        "stress": StressScenarioInput(
            flash_crash_loss_pct=14,
            spread_explosion_loss_pct=2,
            liquidity_removal_loss_pct=4,
            server_delay_loss_pct=1,
            slippage_loss_pct=2,
        )
    })
    record = service.create(data)
    assert record.state == PortfolioOptimizerState.REVIEW_REQUIRED


def test_duplicate_source_key_is_rejected_per_workspace():
    service = AIPortfolioOptimizerService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())


def test_workspace_isolation():
    service = AIPortfolioOptimizerService()
    record = service.create(payload())
    assert service.get(record.id, "other") is None
    assert service.list_records("other") == []
