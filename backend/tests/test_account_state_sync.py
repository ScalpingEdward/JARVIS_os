from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.account_state_sync.models import SyncExecutionRequest
from app.account_state_sync.service import account_state_sync_service
from app.accounts.models import (
    AccountStatus,
    AccountType,
    PropFirmRules,
    TradingAccountCreate,
)
from app.accounts.service import account_registry_service
from app.main import app
from app.mt5_bridge.models import (
    MT5AccountSnapshot,
    MT5SnapshotIngest,
    MT5TerminalRegister,
)
from app.mt5_bridge.service import mt5_bridge_service

client = TestClient(app)


def setup_function() -> None:
    account_registry_service.reset()
    mt5_bridge_service.reset()
    account_state_sync_service.last_sync_at = None
    account_state_sync_service.last_sync_matched = 0
    account_state_sync_service.last_sync_synced = 0


def _register_account(**overrides) -> object:
    data = dict(
        label="FTMO 100k",
        account_type=AccountType.prop,
        broker="FTMO",
        login="1000001",
        server="FTMO-Demo",
        initial_balance=100000.0,
        prop_rules=PropFirmRules(
            max_daily_loss_pct=5.0,
            max_total_drawdown_pct=10.0,
            profit_target_pct=10.0,
        ),
    )
    data.update(overrides)
    return account_registry_service.register_account(TradingAccountCreate(**data))


def _register_mt5_terminal(**overrides) -> object:
    data = dict(
        name="FTMO Terminal 1",
        terminal_path="C:\\Program Files\\FTMO MT5\\terminal64.exe",
        account_login=1000001,
        broker="FTMO",
        server="FTMO-Demo",
    )
    data.update(overrides)
    return mt5_bridge_service.register(MT5TerminalRegister(**data))


def _push_mt5_snapshot(terminal_id, balance=100000.0, equity=100000.0) -> None:
    mt5_bridge_service.ingest(
        terminal_id,
        MT5SnapshotIngest(
            account=MT5AccountSnapshot(
                balance=balance,
                equity=equity,
                margin=0,
                free_margin=equity,
                margin_level=None,
            )
        ),
    )


# -- basic sync scenarios ----------------------------------------------------


def test_sync_with_no_terminals() -> None:
    acc = _register_account()
    summary = account_state_sync_service.sync()
    assert summary.total_accounts == 1
    assert summary.matched_terminals == 0
    assert summary.synced == 0
    assert summary.failed == 1
    assert summary.results[0].account_id == acc.id
    assert summary.results[0].matched_terminal is False
    assert "No matching MT5 terminal" in summary.results[0].error


def test_sync_with_matching_terminal() -> None:
    acc = _register_account()
    term = _register_mt5_terminal()
    _push_mt5_snapshot(term.id, balance=103000, equity=103000)
    summary = account_state_sync_service.sync()
    assert summary.total_accounts == 1
    assert summary.matched_terminals == 1
    assert summary.synced == 1
    assert summary.failed == 0
    result = summary.results[0]
    assert result.matched_terminal is True
    assert result.synced is True
    assert result.balance == 103000
    assert result.equity == 103000
    # Check that the registry was updated
    reloaded = account_registry_service.get_account(acc.id)
    assert reloaded.balance == 103000
    assert reloaded.equity == 103000


def test_sync_with_non_matching_login() -> None:
    _register_account(login="1000001")
    _register_mt5_terminal(account_login=9999999)
    summary = account_state_sync_service.sync()
    assert summary.matched_terminals == 0
    assert summary.synced == 0


def test_sync_with_non_matching_server() -> None:
    _register_account(server="FTMO-Demo")
    _register_mt5_terminal(server="FTMO-Live")
    summary = account_state_sync_service.sync()
    assert summary.matched_terminals == 0
    assert summary.synced == 0


def test_sync_terminal_without_account_snapshot() -> None:
    acc = _register_account()
    term = _register_mt5_terminal()
    # Do NOT push a snapshot -- terminal has no account data
    summary = account_state_sync_service.sync()
    assert summary.matched_terminals == 1
    assert summary.synced == 0
    assert "no account snapshot" in summary.results[0].error.lower()


# -- breach detection --------------------------------------------------------


def test_sync_detects_daily_loss_breach() -> None:
    acc = _register_account()
    term = _register_mt5_terminal()
    # Push a snapshot that breaches the 5% daily loss limit
    _push_mt5_snapshot(term.id, balance=94000, equity=94000)
    summary = account_state_sync_service.sync()
    assert summary.synced == 1
    assert summary.breaches_detected == 1
    result = summary.results[0]
    assert result.breach_detected is True
    # Verify the account is now breached in the registry
    reloaded = account_registry_service.get_account(acc.id)
    assert reloaded.status == AccountStatus.breached


def test_sync_detects_drawdown_breach() -> None:
    acc = _register_account()
    term = _register_mt5_terminal()
    # Push a snapshot that breaches the 10% total drawdown limit
    _push_mt5_snapshot(term.id, balance=89000, equity=89000)
    summary = account_state_sync_service.sync()
    assert summary.breaches_detected == 1
    reloaded = account_registry_service.get_account(acc.id)
    assert reloaded.status == AccountStatus.breached


def test_sync_no_false_breach_on_profit() -> None:
    acc = _register_account()
    term = _register_mt5_terminal()
    _push_mt5_snapshot(term.id, balance=105000, equity=105000)
    summary = account_state_sync_service.sync()
    assert summary.breaches_detected == 0
    reloaded = account_registry_service.get_account(acc.id)
    assert reloaded.status == AccountStatus.active


# -- filtering and force flag ------------------------------------------------


def test_sync_filters_by_account_ids() -> None:
    acc1 = _register_account(login="1000001")
    acc2 = _register_account(login="1000002")
    _register_mt5_terminal(account_login=1000001)
    term2 = _register_mt5_terminal(account_login=1000002)
    _push_mt5_snapshot(term2.id, balance=102000, equity=102000)
    # Sync only acc2
    summary = account_state_sync_service.sync(SyncExecutionRequest(account_ids=[acc2.id]))
    assert summary.total_accounts == 1
    assert summary.synced == 1
    assert summary.results[0].account_id == acc2.id


def test_sync_skips_suspended_by_default() -> None:
    acc = _register_account()
    term = _register_mt5_terminal()
    _push_mt5_snapshot(term.id, balance=103000, equity=103000)
    account_registry_service.suspend(acc.id)
    summary = account_state_sync_service.sync()
    assert summary.total_accounts == 0
    assert summary.synced == 0


def test_sync_includes_suspended_with_force() -> None:
    acc = _register_account()
    term = _register_mt5_terminal()
    _push_mt5_snapshot(term.id, balance=103000, equity=103000)
    account_registry_service.suspend(acc.id)
    summary = account_state_sync_service.sync(SyncExecutionRequest(force=True))
    assert summary.total_accounts == 1
    assert summary.synced == 1


def test_sync_skips_breached_by_default() -> None:
    acc = _register_account()
    term = _register_mt5_terminal()
    _push_mt5_snapshot(term.id, balance=94000, equity=94000)
    # First sync breaches the account
    account_state_sync_service.sync()
    reloaded = account_registry_service.get_account(acc.id)
    assert reloaded.status == AccountStatus.breached
    # Second sync should skip it (not active)
    _push_mt5_snapshot(term.id, balance=95000, equity=95000)
    summary = account_state_sync_service.sync()
    assert summary.total_accounts == 0


def test_sync_includes_breached_with_force() -> None:
    acc = _register_account()
    term = _register_mt5_terminal()
    _push_mt5_snapshot(term.id, balance=94000, equity=94000)
    account_state_sync_service.sync()
    _push_mt5_snapshot(term.id, balance=95000, equity=95000)
    summary = account_state_sync_service.sync(SyncExecutionRequest(force=True))
    assert summary.total_accounts == 1
    assert summary.synced == 1


# -- multiple accounts -------------------------------------------------------


def test_sync_multiple_accounts() -> None:
    acc1 = _register_account(login="1000001", label="Account 1")
    acc2 = _register_account(login="1000002", label="Account 2")
    acc3 = _register_account(login="1000003", label="Account 3")
    term1 = _register_mt5_terminal(account_login=1000001)
    term2 = _register_mt5_terminal(account_login=1000002)
    # acc3 has no matching terminal
    _push_mt5_snapshot(term1.id, balance=101000, equity=101000)
    _push_mt5_snapshot(term2.id, balance=102000, equity=102000)
    summary = account_state_sync_service.sync()
    assert summary.total_accounts == 3
    assert summary.matched_terminals == 2
    assert summary.synced == 2
    assert summary.failed == 1
    # Verify each account was updated correctly
    assert account_registry_service.get_account(acc1.id).equity == 101000
    assert account_registry_service.get_account(acc2.id).equity == 102000
    assert account_registry_service.get_account(acc3.id).equity == 100000  # unchanged


# -- status tracking ---------------------------------------------------------


def test_status_reflects_last_sync() -> None:
    status = account_state_sync_service.status()
    assert status.last_sync_at is None
    assert status.last_sync_matched == 0
    assert status.last_sync_synced == 0
    acc = _register_account()
    term = _register_mt5_terminal()
    _push_mt5_snapshot(term.id)
    account_state_sync_service.sync()
    status = account_state_sync_service.status()
    assert status.last_sync_at is not None
    assert status.last_sync_matched == 1
    assert status.last_sync_synced == 1


# -- API surface -------------------------------------------------------------


def test_api_status() -> None:
    resp = client.get("/v1/account-state-sync/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["module"] == "account-state-sync"
    assert data["version"] == "1.0"


def test_api_sync() -> None:
    acc = _register_account()
    term = _register_mt5_terminal()
    _push_mt5_snapshot(term.id, balance=104000, equity=104000)
    resp = client.post("/v1/account-state-sync/sync", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_accounts"] == 1
    assert data["matched_terminals"] == 1
    assert data["synced"] == 1
    assert data["results"][0]["balance"] == 104000
    assert data["results"][0]["equity"] == 104000


def test_api_sync_with_request_body() -> None:
    acc1 = _register_account(login="1000001")
    acc2 = _register_account(login="1000002")
    term1 = _register_mt5_terminal(account_login=1000001)
    term2 = _register_mt5_terminal(account_login=1000002)
    _push_mt5_snapshot(term1.id)
    _push_mt5_snapshot(term2.id)
    resp = client.post(
        "/v1/account-state-sync/sync",
        json={"account_ids": [str(acc1.id)], "force": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_accounts"] == 1
    assert data["synced"] == 1
