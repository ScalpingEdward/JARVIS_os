from app.executive_shadow_portfolio_simulator.models import (
    ShadowPortfolioCreate,
    ShadowPortfolioExecuteRequest,
    ShadowPortfolioState,
    ShadowTradeInput,
)
from app.executive_shadow_portfolio_simulator.service import ShadowPortfolioSimulatorService


def trade(index: int, pnl: float, rr: float, strategy: str = "ict-gold", slippage: float = 1) -> ShadowTradeInput:
    return ShadowTradeInput(
        trade_id=f"t-{index}", strategy_id=strategy, symbol="XAUUSD", account_id="a-1",
        side="buy", entry_price=2300, exit_price=2301, volume=0.1,
        pnl=pnl, risk_amount=100, realized_rr=rr, slippage_bps=slippage,
        max_adverse_excursion_r=0.5, max_favorable_excursion_r=max(rr, 0), duration_seconds=300,
        routed_by_v19_06=True, market_allowed_by_v19_08=True,
    )


def payload(**overrides) -> ShadowPortfolioCreate:
    trades = []
    for i in range(1, 11):
        trades.append(trade(i, 200, 2))
        trades.append(trade(i + 10, -100, -1))
    data = dict(
        workspace_id="w-1", source_key="shadow-1", actor_id="tester",
        account_risk_approved=True, prop_rules_approved=True, market_permission_approved=True,
        initial_equity=100000, max_daily_loss_pct=5, max_total_drawdown_pct=10,
        min_sample_size=20, promotion_min_trades=30, trades=trades,
    )
    data.update(overrides)
    return ShadowPortfolioCreate(**data)


def test_v1908_market_permission_required():
    service = ShadowPortfolioSimulatorService()
    record = service.create(payload(market_permission_approved=False))
    assert record.state == ShadowPortfolioState.MARKET_PERMISSION_REQUIRED


def test_valid_sample_is_simulation_ready():
    service = ShadowPortfolioSimulatorService()
    record = service.create(payload())
    assert record.state == ShadowPortfolioState.SIMULATION_READY
    assert record.expectancy_r == 0.5
    assert record.profit_factor == 2
    assert record.strategies[0].trades == 20


def test_large_loss_creates_risk_breach():
    service = ShadowPortfolioSimulatorService()
    trades = [trade(i, 100, 1) for i in range(1, 20)] + [trade(20, -12000, -120)]
    record = service.create(payload(trades=trades))
    assert record.state == ShadowPortfolioState.BREACH_DETECTED
    assert record.risk_breaches > 0


def test_promotion_requires_sample_and_human_approval():
    service = ShadowPortfolioSimulatorService()
    trades = [trade(i, 200, 2) if i % 2 else trade(i, -100, -1) for i in range(1, 31)]
    record = service.create(payload(trades=trades, promotion_min_trades=30))
    assert record.state == ShadowPortfolioState.PROMOTION_CANDIDATE
    try:
        service.execute(record.id, "w-1", ShadowPortfolioExecuteRequest(actor_id="tester", action="promote"))
        assert False
    except ValueError as exc:
        assert "human approval" in str(exc)
    promoted = service.execute(record.id, "w-1", ShadowPortfolioExecuteRequest(actor_id="tester", action="promote", human_approved=True))
    assert promoted.state == ShadowPortfolioState.MONITORING


def test_workspace_isolation_and_duplicate_protection():
    service = ShadowPortfolioSimulatorService()
    record = service.create(payload())
    assert service.get(record.id, "other") is None
    try:
        service.create(payload())
        assert False
    except ValueError as exc:
        assert "duplicate" in str(exc)
