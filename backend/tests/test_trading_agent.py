from app.trading.models import (
    MarketBias,
    MarketSnapshot,
    RiskPolicy,
    SetupDecision,
    SetupEvaluationRequest,
    TradeSide,
)
from app.trading.service import trading_agent_service


def setup_function() -> None:
    trading_agent_service.reset()


def _request(**overrides):
    snapshot = MarketSnapshot(
        symbol="XAUUSD",
        timeframe="M15",
        price=2400,
        higher_timeframe_bias=MarketBias.bullish,
        liquidity_sweep=True,
        structure_shift=True,
        fair_value_gap=True,
        order_block=True,
        spread_points=20,
        **overrides,
    )
    return SetupEvaluationRequest(
        snapshot=snapshot,
        policy=RiskPolicy(account_balance=10000, risk_percent=1),
        side=TradeSide.buy,
        entry=2400,
        stop_loss=2390,
        take_profit=2430,
    )


def test_valid_setup_is_advisory_and_requires_human_approval() -> None:
    setup = trading_agent_service.evaluate(_request())
    assert setup.decision == SetupDecision.valid
    assert setup.risk_reward == 3
    assert setup.suggested_risk_amount == 100
    assert setup.human_approval_required is True
    assert setup.automatic_execution_enabled is False


def test_news_risk_blocks_setup() -> None:
    setup = trading_agent_service.evaluate(_request(news_risk=True))
    assert setup.decision == SetupDecision.rejected
    assert "high-impact news risk" in setup.blockers
    assert setup.suggested_risk_amount == 0


def test_daily_drawdown_and_open_trade_limits_block_setup() -> None:
    request = _request()
    request.policy.daily_drawdown_percent = 4
    request.policy.current_open_trades = 3
    setup = trading_agent_service.evaluate(request)
    assert setup.decision == SetupDecision.rejected
    assert "daily drawdown limit reached" in setup.blockers
    assert "maximum open trades reached" in setup.blockers


def test_status_contract_keeps_execution_disabled() -> None:
    status = trading_agent_service.status()
    assert status.advisory_only is True
    assert status.automatic_execution_enabled is False
    assert status.human_approval_required is True
