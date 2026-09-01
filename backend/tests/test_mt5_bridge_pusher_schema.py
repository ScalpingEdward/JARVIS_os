"""The bridge/mt5_pusher.py script cannot run in CI (Windows-only MetaTrader5
package, needs a real logged-in terminal). This test mocks just enough of
the MetaTrader5 module's surface to run collect_snapshot() and validates
the resulting dict against the real MT5SnapshotIngest Pydantic model --
so a field-name mismatch between the pusher script and the backend schema
fails a test instead of only being discovered against a real broker."""

from __future__ import annotations

import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.mt5_bridge.models import MT5SnapshotIngest

BRIDGE_DIR = Path(__file__).resolve().parents[2] / "bridge"


@pytest.fixture()
def mt5_pusher_module(monkeypatch):
    fake_mt5 = types.ModuleType("MetaTrader5")
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.DEAL_TYPE_BUY = 0
    fake_mt5.DEAL_TYPE_SELL = 1

    now = time.time()

    fake_mt5.account_info = lambda: SimpleNamespace(
        balance=100000.0,
        equity=99500.0,
        margin=500.0,
        margin_free=99000.0,
        margin_level=19900.0,
        profit=-500.0,
        currency="USD",
    )
    fake_mt5.positions_get = lambda: (
        SimpleNamespace(
            ticket=1001,
            symbol="EURUSD",
            type=0,
            volume=0.5,
            price_open=1.1000,
            price_current=1.1010,
            sl=1.0950,
            tp=1.1100,
            profit=50.0,
            time=now,
        ),
    )
    fake_mt5.orders_get = lambda: (
        SimpleNamespace(
            ticket=2001,
            symbol="EURUSD",
            type=2,
            volume_current=0.25,
            price_open=1.0900,
            sl=1.0850,
            tp=1.1000,
            time_expiration=0,
        ),
    )
    fake_mt5.history_deals_get = lambda frm, to: (
        SimpleNamespace(
            ticket=3001,
            order=2000,
            symbol="EURUSD",
            type=0,
            volume=0.5,
            price=1.1000,
            profit=25.0,
            commission=-1.5,
            swap=0.0,
            time=now,
        ),
    )
    fake_mt5.symbol_info_tick = lambda symbol: SimpleNamespace(bid=1.10500, ask=1.10510, last=1.10505, time=now)
    fake_mt5.symbol_info = lambda symbol: SimpleNamespace(
        point=0.00001,
        digits=5,
        volume_min=0.01,
        volume_max=50.0,
        volume_step=0.01,
        trade_contract_size=100000.0,
        trade_tick_size=0.00001,
        trade_tick_value=1.0,
    )
    fake_mt5.initialize = lambda: True
    fake_mt5.shutdown = lambda: None
    fake_mt5.last_error = lambda: (0, "no error")

    monkeypatch.setitem(sys.modules, "MetaTrader5", fake_mt5)
    monkeypatch.syspath_prepend(str(BRIDGE_DIR))
    sys.modules.pop("mt5_pusher", None)
    import mt5_pusher  # noqa: PLC0415

    yield mt5_pusher
    sys.modules.pop("mt5_pusher", None)


def test_collect_snapshot_matches_the_real_backend_schema(mt5_pusher_module):
    snapshot = mt5_pusher_module.collect_snapshot(["EURUSD"], deal_history_days=7)

    # This is the actual assertion that matters: if the pusher script's
    # dict shape drifts from the backend model, this raises a validation
    # error and the test fails -- instead of silently breaking ingest
    # against a real terminal.
    validated = MT5SnapshotIngest(**snapshot)

    assert validated.account.balance == pytest.approx(100000.0)
    assert validated.positions[0].symbol == "EURUSD"
    assert validated.positions[0].side == "buy"
    assert validated.pending_orders[0].ticket == 2001
    assert validated.deals[0].side == "buy"
    assert validated.ticks[0].bid == pytest.approx(1.10500)
    assert validated.symbols[0].symbol == "EURUSD"
    assert validated.symbols[0].value_per_price_unit == pytest.approx(100000.0)


def test_collect_snapshot_handles_no_stop_loss_or_take_profit(mt5_pusher_module, monkeypatch):
    now = time.time()
    monkeypatch.setattr(
        sys.modules["MetaTrader5"],
        "positions_get",
        lambda: (
            SimpleNamespace(
                ticket=1002,
                symbol="EURUSD",
                type=0,
                volume=0.1,
                price_open=1.1,
                price_current=1.101,
                sl=0.0,  # MT5 reports 0.0, not None, when no SL/TP is set
                tp=0.0,
                profit=1.0,
                time=now,
            ),
        ),
    )
    snapshot = mt5_pusher_module.collect_snapshot(["EURUSD"], deal_history_days=7)
    validated = MT5SnapshotIngest(**snapshot)
    assert validated.positions[0].stop_loss is None
    assert validated.positions[0].take_profit is None
