from datetime import datetime, timedelta, timezone

import pytest

from app.mt5_bridge.models import (
    MT5AccountSnapshot,
    MT5ConnectionState,
    MT5Heartbeat,
    MT5SnapshotIngest,
    MT5TerminalRegister,
)
from app.mt5_bridge.service import MT5BridgeError, mt5_bridge_service


def setup_function() -> None:
    mt5_bridge_service.reset()


def _terminal():
    return mt5_bridge_service.register(
        MT5TerminalRegister(
            name="FTMO 100K",
            terminal_path=r"C:\\Program Files\\MetaTrader 5\\terminal64.exe",
            account_login=12345678,
            broker="FTMO",
            server="FTMO-Demo",
        )
    )


def test_registration_enforces_read_only_mode() -> None:
    with pytest.raises(MT5BridgeError, match="read-only"):
        mt5_bridge_service.register(
            MT5TerminalRegister(
                name="Unsafe",
                terminal_path="terminal64.exe",
                account_login=99,
                broker="Broker",
                server="Server",
                read_only=False,
            )
        )


def test_heartbeat_connects_terminal_and_status_blocks_execution() -> None:
    terminal = _terminal()
    updated = mt5_bridge_service.heartbeat(terminal.id, MT5Heartbeat(bridge_version="2.1.0", latency_ms=18))
    status = mt5_bridge_service.status()
    assert updated.state == MT5ConnectionState.connected
    assert status.connected == 1
    assert status.read_only_enforced is True
    assert status.order_execution_enabled is False


def test_snapshot_stores_account_and_live_lists() -> None:
    terminal = _terminal()
    snapshot = mt5_bridge_service.ingest(
        terminal.id,
        MT5SnapshotIngest(
            account=MT5AccountSnapshot(
                balance=100000,
                equity=100450,
                margin=500,
                free_margin=99950,
                margin_level=20090,
                floating_pnl=450,
                daily_pnl=720,
            )
        ),
    )
    assert snapshot.account is not None
    assert snapshot.account.equity == 100450
    assert snapshot.terminal.state == MT5ConnectionState.connected


def test_multi_terminal_registration_and_duplicate_protection() -> None:
    _terminal()
    mt5_bridge_service.register(
        MT5TerminalRegister(
            name="Personal",
            terminal_path=r"D:\\MT5\\terminal64.exe",
            account_login=87654321,
            broker="Broker",
            server="Broker-Live",
        )
    )
    assert mt5_bridge_service.status().terminals == 2
    with pytest.raises(MT5BridgeError, match="already registered"):
        _terminal()


def test_stale_and_disconnected_states_are_derived_from_heartbeat_age() -> None:
    terminal = _terminal()
    mt5_bridge_service.heartbeat(terminal.id, MT5Heartbeat(bridge_version="2.1.0", latency_ms=10))
    now = datetime.now(timezone.utc)
    internal = mt5_bridge_service._items[terminal.id]
    internal.terminal.last_heartbeat_at = now - timedelta(seconds=45)
    mt5_bridge_service.refresh_states(now)
    assert internal.terminal.state == MT5ConnectionState.stale
    internal.terminal.last_heartbeat_at = now - timedelta(minutes=3)
    mt5_bridge_service.refresh_states(now)
    assert internal.terminal.state == MT5ConnectionState.disconnected


# -- sequence gap detection ---------------------------------------------


def _ingest(terminal_id, sequence=None):
    return mt5_bridge_service.ingest(terminal_id, MT5SnapshotIngest(
        account=MT5AccountSnapshot(balance=100_000, equity=100_000, margin=0, free_margin=100_000),
        sequence=sequence,
    ))


def test_first_sequence_ever_is_contiguous_by_definition() -> None:
    terminal = _terminal()
    data = _ingest(terminal.id, sequence=1)
    assert data.sequence_contiguous is True
    assert data.last_sequence == 1


def test_consecutive_sequences_stay_contiguous() -> None:
    terminal = _terminal()
    for seq in range(1, 6):
        data = _ingest(terminal.id, sequence=seq)
    assert data.sequence_contiguous is True
    assert data.last_sequence == 5


def test_a_gap_is_detected() -> None:
    terminal = _terminal()
    _ingest(terminal.id, sequence=1)
    _ingest(terminal.id, sequence=2)
    data = _ingest(terminal.id, sequence=5)  # skipped 3 and 4 -- a real dropped push
    assert data.sequence_contiguous is False
    assert data.last_sequence == 5


def test_contiguity_recovers_once_pushes_resume_in_order() -> None:
    """A past gap is not sticky forever -- 'contiguous' reflects whether the
    *most recent* push continued cleanly, so the stream is reported healthy
    again the moment it actually is."""
    terminal = _terminal()
    _ingest(terminal.id, sequence=1)
    _ingest(terminal.id, sequence=5)  # a gap
    data = _ingest(terminal.id, sequence=6)  # back in order
    assert data.sequence_contiguous is True


def test_no_sequence_ever_sent_leaves_contiguous_true_and_last_sequence_unset() -> None:
    """An older/unmodified pusher that never sends a sequence number must
    not be penalized -- there is no evidence of a gap, only an absence of
    the ability to detect one either way."""
    terminal = _terminal()
    data = _ingest(terminal.id, sequence=None)
    assert data.sequence_contiguous is True
    assert data.last_sequence is None


def test_a_restart_resetting_to_a_low_sequence_is_correctly_flagged_as_a_gap() -> None:
    """The pusher does not persist its counter across restarts on purpose
    -- a fresh start is a genuine discontinuity, and the existing check
    already reports that correctly with no special-casing."""
    terminal = _terminal()
    _ingest(terminal.id, sequence=500)
    data = _ingest(terminal.id, sequence=1)  # pusher restarted
    assert data.sequence_contiguous is False
