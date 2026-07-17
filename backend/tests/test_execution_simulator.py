import pytest
from pydantic import ValidationError

from app.execution_simulator.models import (
    BrokerExecutionProfile,
    OrderSide,
    OrderState,
    OrderType,
    SimulationOrderCreate,
)
from app.execution_simulator.service import ExecutionSimulatorService


def profile(**overrides):
    data = {
        "name": "FTMO-Sim",
        "spread_points": 20,
        "slippage_points": 5,
        "latency_ms": 80,
        "partial_fill_probability": 0,
        "commission_per_lot": 3.5,
    }
    data.update(overrides)
    return BrokerExecutionProfile(**data)


def order(**overrides):
    data = {
        "symbol": "XAUUSD",
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "volume": 1,
        "requested_price": 2400,
        "market_price": 2400,
        "point_size": 0.01,
        "execution_profile": profile(),
    }
    data.update(overrides)
    return SimulationOrderCreate(**data)


def test_market_order_is_simulated_without_real_execution():
    service = ExecutionSimulatorService()
    result = service.create(order())
    assert result.state == OrderState.FILLED
    assert result.real_order_sent is False
    assert result.human_approval_required is True
    assert result.average_fill_price == 2400.05


def test_automatic_execution_is_rejected():
    with pytest.raises(ValidationError):
        order(automatic_execution=True)


def test_limit_order_waits_until_trigger():
    service = ExecutionSimulatorService()
    result = service.create(
        order(order_type=OrderType.LIMIT, trigger_price=2390, market_price=2400)
    )
    assert result.state == OrderState.PENDING
    assert "Trigger condition not reached" in result.warnings


def test_partial_fill_and_report():
    service = ExecutionSimulatorService()
    result = service.create(
        order(volume=2, execution_profile=profile(partial_fill_probability=0.8))
    )
    assert result.state == OrderState.PARTIALLY_FILLED
    assert result.filled_volume == 1
    report = service.report()
    assert report.total_orders == 1
    assert report.total_filled_volume == 1
    assert report.total_commission == 3.5


def test_pending_order_can_be_cancelled():
    service = ExecutionSimulatorService()
    pending = service.create(
        order(order_type=OrderType.STOP, trigger_price=2410, market_price=2400)
    )
    cancelled = service.cancel(pending.id)
    assert cancelled is not None
    assert cancelled.state == OrderState.CANCELLED
