"""Tests for strategy orchestrator."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.accounts.models import (
    AccountStateUpdate,
    AccountStatus,
    AccountType,
    DrawdownType,
    PropFirmRules,
    StrategyAssignmentCreate,
    TradingAccountCreate,
)
from app.accounts.service import account_registry_service
from app.main import app
from app.strategies.models import (
    FairValueGap,
    HTFBias,
    MarketSnapshot,
    OrderBlock,
    OrderBlockType,
    StructureLevel,
)
from app.strategy_orchestrator.service import strategy_orchestrator

client = TestClient(app)


def setup_function() -> None:
    account_registry_service.reset()


def _prop_account(**overrides) -> TradingAccountCreate:
    """Create a prop account payload."""
    data = dict(
        label="FTMO 100k",
        account_type=AccountType.prop,
        broker="FTMO",
        login="1000001",
        server="FTMO-Demo",
        currency="USD",
        initial_balance=100000.0,
        prop_rules=PropFirmRules(
            max_daily_loss_pct=5.0,
            max_total_drawdown_pct=10.0,
            profit_target_pct=10.0,
            min_trading_days=4,
            drawdown_type=DrawdownType.static,
        ),
    )
    data.update(overrides)
    return TradingAccountCreate(**data)


def _live_account(**overrides) -> TradingAccountCreate:
    """Create a live account payload."""
    data = dict(
        label="Live XM",
        account_type=AccountType.live,
        broker="XM",
        login="2000001",
        server="XM-Real",
        currency="USD",
        initial_balance=5000.0,
    )
    data.update(overrides)
    return TradingAccountCreate(**data)


def _valid_london_snapshot(**overrides) -> MarketSnapshot:
    """Snapshot that triggers both scalping_3tp and ict_silver_bullet."""
    data = dict(
        symbol="EURUSD",
        current_price=1.10000,
        bid=1.09995,
        ask=1.10005,
        spread=0.00010,
        htf_bias=HTFBias.bullish,
        session="london",
        order_blocks=[
            OrderBlock(
                type=OrderBlockType.bullish,
                high=1.10010,
                low=1.09990,
                open=1.09990,
                close=1.10000,
            )
        ],
        fvgs=[FairValueGap(side="bullish", top=1.10200, bottom=1.09980)],
        structure_levels=[
            StructureLevel(level=1.09900, type="low", strength=3),
            StructureLevel(level=1.10500, type="high", strength=4),
        ],
    )
    data.update(overrides)
    return MarketSnapshot(**data)


def _no_setup_snapshot(**overrides) -> MarketSnapshot:
    """Snapshot that produces no setups (neutral HTF)."""
    data = dict(
        symbol="EURUSD",
        current_price=1.10000,
        bid=1.09995,
        ask=1.10005,
        spread=0.00010,
        htf_bias=HTFBias.neutral,
        session="off",
        order_blocks=[],
        fvgs=[],
        structure_levels=[],
    )
    data.update(overrides)
    return MarketSnapshot(**data)


# -- orchestrator tests ------------------------------------------------------


def test_orchestrate_no_accounts() -> None:
    """Orchestration with zero accounts returns empty results."""
    snapshot = _valid_london_snapshot()
    result = strategy_orchestrator.evaluate_all_accounts(snapshot)
    assert result.total_accounts == 0
    assert result.active_accounts == 0
    assert result.total_evaluations == 0
    assert result.total_valid_setups == 0
    assert result.total_executable_setups == 0
    assert len(result.account_evaluations) == 0


def test_orchestrate_account_no_strategies() -> None:
    """Account without strategy assignments produces zero evaluations."""
    account = account_registry_service.register_account(_prop_account())
    snapshot = _valid_london_snapshot()
    result = strategy_orchestrator.evaluate_all_accounts(snapshot)
    assert result.total_accounts == 1
    assert result.active_accounts == 1
    assert result.total_evaluations == 0  # No strategies assigned
    assert len(result.account_evaluations) == 1
    eval_result = result.account_evaluations[0]
    assert eval_result.account_id == account.id
    assert len(eval_result.assigned_strategies) == 0
    assert len(eval_result.strategy_results) == 0


def test_orchestrate_one_account_one_strategy() -> None:
    """One account with one assigned strategy."""
    account = account_registry_service.register_account(_prop_account())
    account_registry_service.assign_strategy(
        account.id,
        StrategyAssignmentCreate(strategy_id="scalping_3tp", strategy_name="Scalping 3TP", allocation_pct=100),
    )
    snapshot = _valid_london_snapshot()
    result = strategy_orchestrator.evaluate_all_accounts(snapshot)
    assert result.total_accounts == 1
    assert result.active_accounts == 1
    assert result.total_evaluations == 1
    assert result.total_valid_setups == 1  # scalping_3tp produces a setup
    assert result.total_executable_setups == 1  # Account is compliant
    eval_result = result.account_evaluations[0]
    assert eval_result.assigned_strategies == ["scalping_3tp"]
    assert len(eval_result.strategy_results) == 1
    assert len(eval_result.valid_setups) == 1
    assert len(eval_result.executable_setups) == 1
    assert eval_result.compliance_ok is True
    assert eval_result.blocked_reason is None


def test_orchestrate_one_account_two_strategies() -> None:
    """One account with two assigned strategies (both produce setups)."""
    account = account_registry_service.register_account(_prop_account())
    account_registry_service.assign_strategy(
        account.id,
        StrategyAssignmentCreate(strategy_id="scalping_3tp", strategy_name="Scalping 3TP", allocation_pct=50),
    )
    account_registry_service.assign_strategy(
        account.id,
        StrategyAssignmentCreate(strategy_id="ict_silver_bullet", strategy_name="ICT Silver Bullet", allocation_pct=50),
    )
    snapshot = _valid_london_snapshot()
    result = strategy_orchestrator.evaluate_all_accounts(snapshot)
    assert result.total_evaluations == 2
    assert result.total_valid_setups == 2  # Both strategies produce setups
    assert result.total_executable_setups == 2
    eval_result = result.account_evaluations[0]
    assert set(eval_result.assigned_strategies) == {"scalping_3tp", "ict_silver_bullet"}
    assert len(eval_result.strategy_results) == 2
    assert len(eval_result.valid_setups) == 2
    assert len(eval_result.executable_setups) == 2


def test_orchestrate_multiple_accounts() -> None:
    """Multiple accounts with different strategy assignments."""
    # Account 1: scalping_3tp
    acc1 = account_registry_service.register_account(_prop_account(login="1000001"))
    account_registry_service.assign_strategy(
        acc1.id, StrategyAssignmentCreate(strategy_id="scalping_3tp", strategy_name="Scalping 3TP", allocation_pct=100)
    )
    # Account 2: ict_silver_bullet
    acc2 = account_registry_service.register_account(_live_account(login="2000001"))
    account_registry_service.assign_strategy(
        acc2.id,
        StrategyAssignmentCreate(strategy_id="ict_silver_bullet", strategy_name="ICT Silver Bullet", allocation_pct=100),
    )
    snapshot = _valid_london_snapshot()
    result = strategy_orchestrator.evaluate_all_accounts(snapshot)
    assert result.total_accounts == 2
    assert result.active_accounts == 2
    assert result.total_evaluations == 2
    assert result.total_valid_setups == 2
    assert result.total_executable_setups == 2
    assert len(result.account_evaluations) == 2


def test_orchestrate_suspended_account_blocked() -> None:
    """Suspended account produces setups but they are not executable."""
    account = account_registry_service.register_account(_prop_account())
    account_registry_service.assign_strategy(
        account.id,
        StrategyAssignmentCreate(strategy_id="scalping_3tp", strategy_name="Scalping 3TP", allocation_pct=100),
    )
    account_registry_service.suspend(account.id)
    snapshot = _valid_london_snapshot()
    result = strategy_orchestrator.evaluate_all_accounts(snapshot)
    # Suspended account is not active, so it's not even evaluated
    assert result.active_accounts == 0
    assert result.total_evaluations == 0


def test_orchestrate_breached_account_blocked() -> None:
    """Breached account is auto-set to breached status and not evaluated."""
    account = account_registry_service.register_account(_prop_account())
    account_registry_service.assign_strategy(
        account.id,
        StrategyAssignmentCreate(strategy_id="scalping_3tp", strategy_name="Scalping 3TP", allocation_pct=100),
    )
    # Breach the account (daily loss > 5%) -> auto-sets status to 'breached'
    account_registry_service.update_state(
        account.id,
        AccountStateUpdate(balance=94000.0, equity=94000.0, day_start_balance=100000.0),
    )
    snapshot = _valid_london_snapshot()
    result = strategy_orchestrator.evaluate_all_accounts(snapshot)
    # Breached account is not active, so not evaluated by the orchestrator
    assert result.total_accounts == 1
    assert result.active_accounts == 0
    assert result.total_evaluations == 0
    assert result.total_executable_setups == 0


def test_orchestrate_no_setup_conditions() -> None:
    """Snapshot that produces no setups returns zero executable setups."""
    account = account_registry_service.register_account(_prop_account())
    account_registry_service.assign_strategy(
        account.id,
        StrategyAssignmentCreate(strategy_id="scalping_3tp", strategy_name="Scalping 3TP", allocation_pct=100),
    )
    snapshot = _no_setup_snapshot()
    result = strategy_orchestrator.evaluate_all_accounts(snapshot)
    assert result.total_evaluations == 1
    assert result.total_valid_setups == 0  # No setups produced
    assert result.total_executable_setups == 0


# -- API tests ---------------------------------------------------------------


def test_api_evaluate_empty() -> None:
    """API endpoint with zero accounts."""
    snapshot = _valid_london_snapshot().model_dump(mode='json')
    resp = client.post("/v1/strategy-orchestrator/evaluate", json=snapshot)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_accounts"] == 0
    assert data["total_executable_setups"] == 0


def test_api_evaluate_with_accounts() -> None:
    """API endpoint with accounts and strategies."""
    account = account_registry_service.register_account(_prop_account())
    account_registry_service.assign_strategy(
        account.id,
        StrategyAssignmentCreate(strategy_id="scalping_3tp", strategy_name="Scalping 3TP", allocation_pct=100),
    )
    snapshot = _valid_london_snapshot().model_dump(mode='json')
    resp = client.post("/v1/strategy-orchestrator/evaluate", json=snapshot)
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "EURUSD"
    assert data["total_accounts"] == 1
    assert data["active_accounts"] == 1
    assert data["total_evaluations"] == 1
    assert data["total_valid_setups"] == 1
    assert data["total_executable_setups"] == 1
    assert len(data["account_evaluations"]) == 1
    eval_data = data["account_evaluations"][0]
    assert eval_data["assigned_strategies"] == ["scalping_3tp"]
    assert eval_data["compliance_ok"] is True
    assert len(eval_data["executable_setups"]) == 1
