"""bridge/mt5_execution_agent.py cannot run in CI (Windows-only package,
needs a real terminal + real broker). This test mocks just enough of the
MetaTrader5 module to run build_mt5_request() and execute_one() for real,
and validates the resulting report against the actual RemoteExecutionReport
Pydantic model -- so a field-name mismatch fails a test instead of only
being discoverable against a real broker."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.executive_mt5_live_order_executor.models import RemoteExecutionReport

BRIDGE_DIR = Path(__file__).resolve().parents[2] / "bridge"


@pytest.fixture()
def execution_agent_module(monkeypatch):
    fake_mt5 = types.ModuleType("MetaTrader5")
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.ORDER_TYPE_BUY_LIMIT = 2
    fake_mt5.ORDER_TYPE_SELL_LIMIT = 3
    fake_mt5.ORDER_TYPE_BUY_STOP = 4
    fake_mt5.ORDER_TYPE_SELL_STOP = 5
    fake_mt5.TRADE_ACTION_DEAL = 1
    fake_mt5.TRADE_ACTION_PENDING = 5
    fake_mt5.ORDER_TIME_GTC = 0
    fake_mt5.ORDER_FILLING_IOC = 1

    fake_mt5.symbol_info = lambda symbol: SimpleNamespace(name=symbol)
    fake_mt5.symbol_info_tick = lambda symbol: SimpleNamespace(bid=4308.70, ask=4309.02)
    fake_mt5.order_check = lambda request: SimpleNamespace(retcode=0, comment="ok")
    fake_mt5.order_send = lambda request: SimpleNamespace(
        retcode=10009, order=555, deal=777, comment="done", volume=request["volume"], price=request["price"]
    )
    fake_mt5.initialize = lambda: True
    fake_mt5.shutdown = lambda: None
    fake_mt5.last_error = lambda: (0, "no error")

    monkeypatch.setitem(sys.modules, "MetaTrader5", fake_mt5)
    monkeypatch.syspath_prepend(str(BRIDGE_DIR))
    sys.modules.pop("mt5_execution_agent", None)
    import mt5_execution_agent  # noqa: PLC0415

    yield mt5_execution_agent, fake_mt5
    sys.modules.pop("mt5_execution_agent", None)


def _order(**overrides) -> dict:
    request = {
        "symbol": "XAUUSD.s",
        "side": "buy",
        "order_type": "market",
        "volume": 0.13864,
        "requested_price": None,
        "stop_loss": 4304.85,
        "take_profit": None,
        "quote_bid": 4308.70,
        "quote_ask": 4309.02,
        "max_deviation_points": 30,
        "magic": 0,
        "comment": "AURON",
    }
    request.update(overrides)
    return {"id": "test-record-id", "request": request}


def test_build_mt5_request_maps_market_buy_correctly(execution_agent_module):
    agent, fake_mt5 = execution_agent_module
    native = agent.build_mt5_request(_order())
    assert native["symbol"] == "XAUUSD.s"
    assert native["type"] == fake_mt5.ORDER_TYPE_BUY
    assert native["action"] == fake_mt5.TRADE_ACTION_DEAL
    assert native["price"] == pytest.approx(4309.02)  # ask, for a market buy
    assert native["sl"] == pytest.approx(4304.85)
    assert "tp" not in native  # take_profit was None


def test_build_mt5_request_maps_market_sell_to_bid(execution_agent_module):
    agent, fake_mt5 = execution_agent_module
    native = agent.build_mt5_request(_order(side="sell"))
    assert native["type"] == fake_mt5.ORDER_TYPE_SELL
    assert native["price"] == pytest.approx(4308.70)  # bid, for a market sell


def test_execute_one_returns_a_report_valid_against_the_real_schema(execution_agent_module):
    agent, _ = execution_agent_module
    report = agent.execute_one(_order())

    # This is the real check: does the agent's real output actually satisfy
    # the backend's real Pydantic model, not just "some dict with keys".
    validated = RemoteExecutionReport(**report)
    assert validated.broker_retcode == 10009
    assert validated.broker_order_id == 555
    assert validated.broker_deal_id == 777
    assert validated.filled_volume == pytest.approx(0.13864)


def test_execute_one_reports_order_check_rejection_without_calling_order_send(execution_agent_module, monkeypatch):
    agent, fake_mt5 = execution_agent_module
    monkeypatch.setattr(fake_mt5, "order_check", lambda request: SimpleNamespace(retcode=10013, comment="invalid"))

    def _should_not_be_called(request):
        raise AssertionError("order_send must not be called when order_check rejects")

    monkeypatch.setattr(fake_mt5, "order_send", _should_not_be_called)

    report = agent.execute_one(_order())
    validated = RemoteExecutionReport(**report)
    assert validated.broker_retcode == 10013
    assert validated.filled_volume == 0


def test_execute_one_handles_missing_symbol_info_gracefully(execution_agent_module, monkeypatch):
    agent, fake_mt5 = execution_agent_module
    monkeypatch.setattr(fake_mt5, "symbol_info", lambda symbol: None)

    report = agent.execute_one(_order())
    validated = RemoteExecutionReport(**report)
    assert validated.filled_volume == 0
    assert "unavailable" in validated.broker_comment.lower()


def test_execute_one_never_raises_even_on_unexpected_error(execution_agent_module, monkeypatch):
    agent, fake_mt5 = execution_agent_module

    def _boom(symbol):
        raise RuntimeError("terminal disconnected")

    monkeypatch.setattr(fake_mt5, "symbol_info", _boom)

    report = agent.execute_one(_order())  # must not raise
    validated = RemoteExecutionReport(**report)
    assert "terminal disconnected" in validated.broker_comment
