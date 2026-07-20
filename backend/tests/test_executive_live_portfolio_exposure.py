import pytest

from app.executive_live_portfolio_exposure.models import (
    LiveExposurePosition,
    LivePortfolioExposureCreate,
    PortfolioExposurePolicy,
    PortfolioState,
)
from app.executive_live_portfolio_exposure.service import ExecutiveLivePortfolioExposureService


def position(**overrides):
    data = dict(
        broker_id="broker-a",
        account_id="live-1",
        symbol="XAUUSD",
        strategy_id="ict",
        currency="EUR",
        allocated_capital=2500,
        risk_amount=50,
        correlation_group="metals",
    )
    data.update(overrides)
    return LiveExposurePosition(**data)


def payload(**overrides):
    data = dict(
        workspace_id="ws-1",
        source_key="portfolio-1",
        actor_id="master-brano",
        total_live_owned_capital=10000,
        current_drawdown=100,
        human_approved=True,
        risk_brain_clear=True,
        positions=[
            position(),
            position(broker_id="broker-b", account_id="live-2", symbol="EURUSD", strategy_id="swing", correlation_group="fx"),
            position(broker_id="broker-a", account_id="live-3", symbol="BTCUSD", strategy_id="algo", correlation_group="crypto"),
            position(broker_id="broker-b", account_id="live-4", symbol="USDJPY", strategy_id="manual", correlation_group="fx-2"),
        ],
        policy=PortfolioExposurePolicy(max_broker_share=0.5, max_symbol_share=0.3, max_strategy_share=0.3, max_currency_share=1.0, max_correlation_group_share=0.35),
    )
    data.update(overrides)
    return LivePortfolioExposureCreate(**data)


def test_fully_allocated_balanced_portfolio():
    service = ExecutiveLivePortfolioExposureService()
    result = service.create(payload())
    assert result.state == PortfolioState.fully_allocated
    assert result.allocated_capital == 10000
    assert result.unallocated_capital == 0


def test_concentration_requires_rebalance():
    service = ExecutiveLivePortfolioExposureService()
    result = service.create(payload(positions=[position(allocated_capital=8000), position(broker_id="broker-b", account_id="live-2", allocated_capital=2000)]))
    assert result.state == PortfolioState.rebalance
    assert any(line.breached for line in result.exposure_lines)


def test_risk_brain_blocks_portfolio():
    service = ExecutiveLivePortfolioExposureService()
    assert service.create(payload(risk_brain_clear=False)).state == PortfolioState.blocked


def test_human_approval_holds_portfolio():
    service = ExecutiveLivePortfolioExposureService()
    assert service.create(payload(human_approved=False)).state == PortfolioState.hold


def test_workspace_isolation_and_duplicate_protection():
    service = ExecutiveLivePortfolioExposureService()
    created = service.create(payload())
    assert service.get(created.id, "other") is None
    with pytest.raises(ValueError):
        service.create(payload())
