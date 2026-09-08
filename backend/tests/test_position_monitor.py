from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.accounts.models import AccountType, TradingAccountCreate
from app.accounts.service import AccountRegistryService
from app.executive_mt5_break_even_scale_out.service import ExecutiveMT5BreakEvenScaleOutService
from app.executive_mt5_position_stream_trailing_stop.models import PositionStreamState
from app.executive_mt5_position_stream_trailing_stop.service import (
    ExecutiveMT5PositionStreamTrailingStopService,
)
from app.mt5_bridge.models import (
    MT5AccountSnapshot,
    MT5Position,
    MT5SnapshotIngest,
    MT5SymbolSpec,
    MT5TerminalRegister,
    MT5Tick,
)
from app.mt5_bridge.service import MT5BridgeService
from app.position_monitor.service import PositionMonitorService

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
LOGIN = 555001


@pytest.fixture()
def rig(tmp_path):
    accounts = AccountRegistryService(db_path=tmp_path / "accounts.db")
    bridge = MT5BridgeService()
    break_even = ExecutiveMT5BreakEvenScaleOutService()
    trailing = ExecutiveMT5PositionStreamTrailingStopService()
    monitor = PositionMonitorService(
        break_even_service=break_even, trailing_service=trailing,
        bridge_service=bridge, accounts_service=accounts, clock=lambda: NOW,
    )
    return monitor, accounts, bridge, break_even, trailing


def _register_account(accounts: AccountRegistryService, login: int = LOGIN):
    return accounts.register_account(TradingAccountCreate(
        label="Demo", account_type=AccountType.demo, broker="TestBroker",
        login=str(login), server="Test-Server", currency="USD", initial_balance=100_000.0,
    ))


def _register_terminal(bridge: MT5BridgeService, login: int = LOGIN):
    return bridge.register(MT5TerminalRegister(
        name="Terminal", terminal_path="C:/MT5/terminal64.exe",
        account_login=login, broker="TestBroker", server="Test-Server",
    ))


def _push_position(
    bridge: MT5BridgeService, terminal_id, *, ticket=900001, symbol="EURUSD",
    side="buy", volume=0.5, open_price=1.10000, current_price=1.10300,
    stop_loss=1.09900, take_profit=None, bid=1.10295, ask=1.10305,
):
    bridge.ingest(terminal_id, MT5SnapshotIngest(
        account=MT5AccountSnapshot(balance=100_000, equity=100_000, margin=0, free_margin=100_000),
        positions=[MT5Position(
            ticket=ticket, symbol=symbol, side=side, volume=volume,
            open_price=open_price, current_price=current_price,
            stop_loss=stop_loss, take_profit=take_profit, opened_at=NOW - timedelta(hours=1),
        )],
        ticks=[MT5Tick(symbol=symbol, bid=bid, ask=ask, captured_at=NOW)],
        symbols=[MT5SymbolSpec(
            symbol=symbol, point=0.00001, digits=5, volume_min=0.01, volume_max=50.0,
            volume_step=0.01, trade_contract_size=100_000, trade_tick_size=0.00001, trade_tick_value=1.0,
        )],
    ))


# -- the basic pass ------------------------------------------------------


def test_a_live_position_gets_both_assessments(rig):
    monitor, accounts, bridge, break_even, trailing = rig
    account = _register_account(accounts)
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id)

    result = monitor.tick()

    assert len(result.assessed) == 1
    row = result.assessed[0]
    assert row.workspace_id == str(account.id)
    assert row.position_ticket == 900001
    assert row.break_even_assessment_id is not None
    assert row.trailing_stream_id is not None
    assert result.skipped == []


def test_trailing_reaches_approval_required_when_genuinely_connected(rig):
    """The fix: once the terminal is really connected (heartbeat/ingest
    fresh) and no sequence gap was ever detected, trailing is no longer
    forced into stream-unavailable -- it genuinely activates and, with
    enough favorable movement, reaches approval-required for real."""
    monitor, accounts, bridge, break_even, trailing = rig
    _register_account(accounts)
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id, open_price=1.10000, stop_loss=1.09900, current_price=1.10500)

    result = monitor.tick()
    assert result.assessed[0].trailing_state == "approval-required"


def test_trailing_honestly_reports_stream_unavailable_when_disconnected(rig):
    """Still honest, not optimistic: a terminal that has gone stale/
    disconnected (no recent heartbeat or ingest) must not be reported as
    trailing-capable just because it was connected a while ago."""
    monitor, accounts, bridge, break_even, trailing = rig
    _register_account(accounts)
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id, open_price=1.10000, stop_loss=1.09900, current_price=1.10500)

    # Simulate the terminal having gone silent well past the staleness window.
    internal = bridge._items[terminal.id]
    internal.terminal.last_heartbeat_at = NOW - timedelta(minutes=5)
    bridge.refresh_states(NOW)

    result = monitor.tick()
    assert result.assessed[0].trailing_state == PositionStreamState.stream_unavailable.value


def test_trailing_honestly_reports_a_detected_sequence_gap(rig):
    monitor, accounts, bridge, break_even, trailing = rig
    _register_account(accounts)
    terminal = _register_terminal(bridge)
    bridge.ingest(terminal.id, MT5SnapshotIngest(
        account=MT5AccountSnapshot(balance=100_000, equity=100_000, margin=0, free_margin=100_000),
        sequence=1,
    ))
    bridge.ingest(terminal.id, MT5SnapshotIngest(
        account=MT5AccountSnapshot(balance=100_000, equity=100_000, margin=0, free_margin=100_000),
        sequence=5,  # a real dropped push -- 2, 3, 4 never arrived
    ))
    _push_position(bridge, terminal.id, open_price=1.10000, stop_loss=1.09900, current_price=1.10500)

    result = monitor.tick()
    assert result.assessed[0].trailing_state == PositionStreamState.event_gap_detected.value


def test_trailing_reaching_approval_required_does_not_yet_satisfy_break_evens_stricter_gate(rig):
    """A precise correction to the previous session's finding: trailing_state
    == "trailing-active" is trailing_stream's own FULLY-EXECUTED terminal
    state (reached only after human_approval_verified, broker
    acknowledgment, and reconciliation) -- not "trailing is currently
    functioning". Trailing reaching approval-required (a real, computed
    proposal, genuinely new behavior after this fix) is progress, but it
    is not the same thing break-even's gate is asking for. This is
    deliberate sequencing in break_even_scale_out's own original design
    (confirm trailing protection is truly, fully active before also
    moving to break-even), not a leftover bug this session failed to
    close -- both steps correctly remain gated behind explicit human
    action, in the right order."""
    monitor, accounts, bridge, break_even, trailing = rig
    account = _register_account(accounts)
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id, open_price=1.10000, stop_loss=1.09900, current_price=1.10500)

    result = monitor.tick()
    assert result.assessed[0].trailing_state == "approval-required", \
        "trailing itself now genuinely proposes -- this part is the real fix"
    assert result.assessed[0].break_even_state == "trailing-required", \
        "break-even correctly still waits for trailing to be FULLY executed, not just proposed"


def test_no_live_positions_is_a_clean_empty_tick(rig):
    monitor, accounts, bridge, *_ = rig
    _register_account(accounts)
    _register_terminal(bridge)
    result = monitor.tick()
    assert result.assessed == [] and result.skipped == []


# -- honest skipping, never guessing --------------------------------------


def test_a_position_under_an_unregistered_login_is_skipped_with_a_reason(rig):
    monitor, accounts, bridge, *_ = rig
    terminal = _register_terminal(bridge)  # no matching AURON account registered
    _push_position(bridge, terminal.id)

    result = monitor.tick()
    assert result.assessed == []
    assert len(result.skipped) == 1
    assert "no AURON account registered" in result.skipped[0].reason
    assert result.skipped[0].position_ticket == 900001


def test_a_position_with_no_symbol_data_yet_is_skipped(rig):
    monitor, accounts, bridge, *_ = rig
    _register_account(accounts)
    terminal = _register_terminal(bridge)
    # ingest a position but with no matching tick/symbol for its symbol
    bridge.ingest(terminal.id, MT5SnapshotIngest(
        account=MT5AccountSnapshot(balance=100_000, equity=100_000, margin=0, free_margin=100_000),
        positions=[MT5Position(
            ticket=1, symbol="GBPUSD", side="buy", volume=0.1,
            open_price=1.25, current_price=1.26, stop_loss=1.24, opened_at=NOW,
        )],
    ))
    result = monitor.tick()
    assert result.assessed == []
    assert "no symbol spec or tick" in result.skipped[0].reason


def test_a_position_with_no_stop_loss_skips_break_even_but_still_gets_trailing(rig):
    monitor, accounts, bridge, *_ = rig
    _register_account(accounts)
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id, stop_loss=None)

    result = monitor.tick()
    assert result.assessed[0].break_even_assessment_id is None
    assert result.assessed[0].trailing_stream_id is not None
    assert any("no stop-loss set" in s.reason for s in result.skipped)


# -- the derived values are real, not invented ----------------------------


def test_trigger_points_is_the_positions_own_1r_distance(rig):
    monitor, accounts, bridge, break_even, trailing = rig
    account = _register_account(accounts)
    terminal = _register_terminal(bridge)
    # 1.10000 entry, 1.09900 stop -> 0.00100 risk -> 100 points at point=0.00001
    _push_position(bridge, terminal.id, open_price=1.10000, stop_loss=1.09900)

    result = monitor.tick()
    record = break_even.get(result.assessed[0].break_even_assessment_id, str(account.id))
    assert record.trigger_points == pytest.approx(100.0)


def test_break_even_offset_is_the_current_spread(rig):
    monitor, accounts, bridge, break_even, trailing = rig
    account = _register_account(accounts)
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id, bid=1.10295, ask=1.10305)  # 10-point spread

    result = monitor.tick()
    record = break_even.get(result.assessed[0].break_even_assessment_id, str(account.id))
    assert record.spread_points == pytest.approx(10.0)
    assert record.break_even_offset_points == pytest.approx(10.0)


def test_observed_rr_reflects_real_unrealized_progress(rig):
    monitor, accounts, bridge, break_even, trailing = rig
    account = _register_account(accounts)
    terminal = _register_terminal(bridge)
    # entry 1.10000, stop 1.09900 (100 pt risk), current 1.10300 -> 300 pt favorable -> 3R
    _push_position(bridge, terminal.id, open_price=1.10000, stop_loss=1.09900, current_price=1.10300)

    result = monitor.tick()
    record = break_even.get(result.assessed[0].break_even_assessment_id, str(account.id))
    assert record.observed_rr == pytest.approx(3.0, abs=0.05)


def test_a_short_position_computes_favorable_direction_correctly(rig):
    monitor, accounts, bridge, break_even, trailing = rig
    account = _register_account(accounts)
    terminal = _register_terminal(bridge)
    _push_position(
        bridge, terminal.id, side="sell", open_price=1.10000, stop_loss=1.10100,
        current_price=1.09800, bid=1.09795, ask=1.09805,
    )
    result = monitor.tick()
    record = break_even.get(result.assessed[0].break_even_assessment_id, str(account.id))
    assert record.observed_rr > 0, "price moved favorably for a short -- must not read as negative/zero"


def test_human_approved_is_always_false_for_an_automatic_assessment(rig):
    """The whole safety property: this only ever proposes."""
    monitor, accounts, bridge, break_even, trailing = rig
    account = _register_account(accounts)
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id)

    result = monitor.tick()
    record = break_even.get(result.assessed[0].break_even_assessment_id, str(account.id))
    assert record.human_approved is False
    assert record.command_dispatched is False


def test_a_breached_account_is_reflected_as_risk_not_clear(rig):
    monitor, accounts, bridge, break_even, trailing = rig
    from app.accounts.models import AccountStateUpdate, DrawdownType, PropFirmRules

    account = accounts.register_account(TradingAccountCreate(
        label="Prop", account_type=AccountType.prop, broker="PropX",
        login=str(LOGIN), server="Test-Server", currency="USD", initial_balance=100_000.0,
        prop_rules=PropFirmRules(max_daily_loss_pct=5.0, max_total_drawdown_pct=10.0,
                                 profit_target_pct=8.0, min_trading_days=5,
                                 drawdown_type=DrawdownType.static),
    ))
    accounts.update_state(account.id, AccountStateUpdate(balance=90_000.0, equity=90_000.0))  # -10% breach
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id)

    result = monitor.tick()
    record = break_even.get(result.assessed[0].break_even_assessment_id, str(account.id))
    assert record.risk_approved is False
    assert record.prop_rules_approved is False


# -- repeat ticks: no crash on the duplicate-key constraint ----------------


def test_two_ticks_in_the_same_second_do_not_collide(rig):
    """create()/assess() refuse a duplicate source_key -- the timestamp
    alone is not enough if two ticks land in the same wall-clock second.
    This must not raise; every tick must produce a usable result."""
    monitor, accounts, bridge, *_ = rig
    _register_account(accounts)
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id)

    first = monitor.tick()
    second = monitor.tick()  # same NOW (fixed clock) -- same second, deliberately
    assert first.assessed[0].break_even_assessment_id != second.assessed[0].break_even_assessment_id


def test_status_reflects_the_last_tick(rig):
    monitor, accounts, bridge, *_ = rig
    _register_account(accounts)
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id)

    monitor.tick()
    status = monitor.status()
    assert status.ticks_run == 1
    assert status.last_tick_assessed == 1
    assert status.last_tick_at == NOW


# -- the loop wrapper: thin, but its two properties matter -----------------


def test_start_and_stop_the_background_loop(rig):
    import asyncio

    monitor, accounts, bridge, *_ = rig
    _register_account(accounts)
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id)

    async def run():
        monitor.start(interval_seconds=0.01)
        await asyncio.sleep(0.05)  # a few ticks
        await monitor.stop()

    asyncio.run(run())
    assert monitor.status().ticks_run >= 1
    assert monitor.status().enabled is False


def test_a_failing_tick_does_not_kill_the_loop(rig):
    """Same task-isolation principle as the trading worker: one bad pass
    must not silently stop all future monitoring."""
    import asyncio

    monitor, accounts, bridge, *_ = rig

    calls = {"n": 0}
    real_tick = monitor.tick

    def flaky_tick():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real_tick()

    monitor.tick = flaky_tick

    async def run():
        monitor.start(interval_seconds=0.01)
        await asyncio.sleep(0.05)
        await monitor.stop()

    asyncio.run(run())
    assert calls["n"] >= 2, "the loop kept going after the first tick raised"


def test_starting_twice_does_not_spawn_a_second_task(rig):
    import asyncio

    monitor, *_ = rig

    async def run():
        monitor.start(interval_seconds=0.05)
        first_task = monitor._task
        monitor.start(interval_seconds=0.05)  # should be a no-op
        assert monitor._task is first_task
        await monitor.stop()

    asyncio.run(run())


# -- the original-stop baseline: pinned once, never recomputed from a --
# -- possibly-already-moved current stop --------------------------------


def test_trigger_points_stays_pinned_after_the_stop_is_moved(rig):
    """The whole point of the fix: once a stop moves (a real break-even
    execution, or by hand), 1R must not shrink toward zero on the next
    tick just because the current stop is now much closer to price."""
    monitor, accounts, bridge, break_even, trailing = rig
    account = _register_account(accounts)
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id, open_price=1.10000, stop_loss=1.09900)  # 100pt risk

    first = monitor.tick()
    first_record = break_even.get(first.assessed[0].break_even_assessment_id, str(account.id))
    assert first_record.trigger_points == pytest.approx(100.0)

    # Simulate the broker reporting the stop already moved to break-even.
    _push_position(bridge, terminal.id, open_price=1.10000, stop_loss=1.10005, current_price=1.10350)

    second = monitor.tick()
    second_record = break_even.get(second.assessed[0].break_even_assessment_id, str(account.id))
    assert second_record.trigger_points == pytest.approx(100.0), \
        "must still use the ORIGINAL 100pt risk, not the now-tiny distance to the moved stop"


def test_two_different_tickets_get_independent_baselines(rig):
    monitor, accounts, bridge, break_even, trailing = rig
    account = _register_account(accounts)
    terminal = _register_terminal(bridge)
    bridge.ingest(terminal.id, MT5SnapshotIngest(
        account=MT5AccountSnapshot(balance=100_000, equity=100_000, margin=0, free_margin=100_000),
        positions=[
            MT5Position(ticket=1, symbol="EURUSD", side="buy", volume=0.1,
                       open_price=1.10000, current_price=1.10200, stop_loss=1.09900, opened_at=NOW),
            MT5Position(ticket=2, symbol="EURUSD", side="buy", volume=0.1,
                       open_price=1.10000, current_price=1.10200, stop_loss=1.09950, opened_at=NOW),
        ],
        ticks=[MT5Tick(symbol="EURUSD", bid=1.10195, ask=1.10205, captured_at=NOW)],
        symbols=[MT5SymbolSpec(symbol="EURUSD", point=0.00001, digits=5, volume_min=0.01,
                               volume_max=50.0, volume_step=0.01, trade_contract_size=100_000,
                               trade_tick_size=0.00001, trade_tick_value=1.0)],
    ))
    result = monitor.tick()
    by_ticket = {a.position_ticket: a for a in result.assessed}
    rec1 = break_even.get(by_ticket[1].break_even_assessment_id, str(account.id))
    rec2 = break_even.get(by_ticket[2].break_even_assessment_id, str(account.id))
    assert rec1.trigger_points == pytest.approx(100.0)
    assert rec2.trigger_points == pytest.approx(50.0)


# -- notification: exactly once per transition into an actionable state ----


class FakeTelegram:
    def __init__(self, raises=None):
        self.calls: list[tuple[str, str]] = []
        self._raises = raises

    def send(self, title, message):
        self.calls.append((title, message))
        if self._raises:
            raise self._raises


def _rig_with_fake_telegram(tmp_path):
    fake = FakeTelegram()
    accounts = AccountRegistryService(db_path=tmp_path / "accounts.db")
    bridge = MT5BridgeService()
    break_even = ExecutiveMT5BreakEvenScaleOutService()
    trailing = ExecutiveMT5PositionStreamTrailingStopService()
    monitor = PositionMonitorService(
        break_even_service=break_even, trailing_service=trailing, bridge_service=bridge,
        accounts_service=accounts, telegram_client=fake, clock=lambda: NOW,
    )
    return monitor, accounts, bridge, break_even, fake


def test_break_even_is_also_structurally_blocked_by_the_honest_trailing_precondition(tmp_path):
    """The finding from the previous session, still true in the one case
    where trailing genuinely cannot be honest: a terminal that really is
    disconnected. break_even_scale_out's own evaluation logic (not this
    module's) requires trailing_state == "trailing-active" before it will
    even look at the trigger -- when trailing correctly and honestly
    reports stream-unavailable (because the terminal really is down),
    break-even correctly refuses to compute a stop off that false
    precondition either. This is no longer the *permanent* state (see the
    now-fixed test above, where a genuinely connected terminal lets both
    modules reach approval-required for real) -- it is the correct
    behavior specifically when the underlying connection really is bad."""
    monitor, accounts, bridge, break_even, fake = _rig_with_fake_telegram(tmp_path)
    _register_account(accounts)
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id, open_price=1.10000, stop_loss=1.09900, current_price=1.10500)
    internal = bridge._items[terminal.id]
    internal.terminal.last_heartbeat_at = NOW - timedelta(minutes=5)
    bridge.refresh_states(NOW)

    result = monitor.tick()
    assert result.assessed[0].break_even_state == "trailing-required"
    assert result.assessed[0].break_even_notified is False
    assert fake.calls == []


def test_notifies_once_when_break_even_becomes_actionable(tmp_path):
    """Unit-tests the notification logic directly, since tick() cannot
    reach an actionable break-even state under today's honest trailing
    precondition (see the test above) -- this proves the logic itself is
    correct and ready for when it can."""
    monitor, accounts, bridge, break_even, fake = _rig_with_fake_telegram(tmp_path)
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id)
    position = bridge.list()[0].positions[0]

    notified = monitor._notify_if_newly_actionable(position, "approval-required")
    assert notified is True
    assert len(fake.calls) == 1
    assert "approval-required" in fake.calls[0][1]
    assert str(position.ticket) in fake.calls[0][1]


def test_does_not_notify_again_for_the_same_ongoing_state(tmp_path):
    monitor, accounts, bridge, break_even, fake = _rig_with_fake_telegram(tmp_path)
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id)
    position = bridge.list()[0].positions[0]

    first = monitor._notify_if_newly_actionable(position, "approval-required")
    second = monitor._notify_if_newly_actionable(position, "approval-required")
    assert first is True and second is False
    assert len(fake.calls) == 1, "must not page again for a state that has not changed"


def test_does_not_notify_for_a_non_actionable_state(tmp_path):
    monitor, accounts, bridge, break_even, fake = _rig_with_fake_telegram(tmp_path)
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id)
    position = bridge.list()[0].positions[0]

    assert monitor._notify_if_newly_actionable(position, "trigger-not-reached") is False
    assert monitor._notify_if_newly_actionable(position, "trailing-required") is False
    assert fake.calls == []


def test_notifies_again_after_a_different_actionable_state(tmp_path):
    """risk-rejected and approval-required are both actionable but
    distinct -- transitioning between them should still notify."""
    monitor, accounts, bridge, break_even, fake = _rig_with_fake_telegram(tmp_path)
    terminal = _register_terminal(bridge)
    _push_position(bridge, terminal.id)
    position = bridge.list()[0].positions[0]

    first = monitor._notify_if_newly_actionable(position, "risk-rejected")
    second = monitor._notify_if_newly_actionable(position, "approval-required")
    assert first is True and second is True
    assert len(fake.calls) == 2


def test_a_telegram_delivery_failure_does_not_raise():
    from app.notification_hub.telegram_delivery import TelegramDeliveryError
    from app.mt5_bridge.models import MT5Position
    from datetime import datetime, timezone

    fake = FakeTelegram(raises=TelegramDeliveryError("no bot token configured"))
    monitor = PositionMonitorService(telegram_client=fake, clock=lambda: NOW)
    position = MT5Position(ticket=1, symbol="EURUSD", side="buy", volume=0.1,
                           open_price=1.1, current_price=1.11, stop_loss=1.09,
                           opened_at=datetime.now(timezone.utc))

    notified = monitor._notify_if_newly_actionable(position, "approval-required")  # must not raise
    assert notified is True  # the attempt counts, even though delivery failed
