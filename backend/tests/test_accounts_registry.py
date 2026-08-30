from __future__ import annotations

import pytest
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
from app.accounts.service import AccountRegistryError, AccountRegistryService, account_registry_service
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    account_registry_service.reset()


@pytest.fixture()
def service(tmp_path) -> AccountRegistryService:
    return AccountRegistryService(db_path=tmp_path / "accounts.db")


def _prop_payload(**overrides) -> TradingAccountCreate:
    data = dict(
        label="FTMO Challenge 100k",
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


# -- registration ------------------------------------------------------------


def test_register_prop_account(service: AccountRegistryService) -> None:
    record = service.register_account(_prop_payload())
    assert record.account_type == AccountType.prop
    assert record.status == AccountStatus.active
    assert record.balance == 100000.0
    assert record.equity == 100000.0
    assert record.prop_rules is not None
    assert record.prop_rules.max_daily_loss_pct == 5.0


def test_register_live_and_demo_without_rules(service: AccountRegistryService) -> None:
    live = service.register_account(
        TradingAccountCreate(
            label="Live IC Markets",
            account_type=AccountType.live,
            broker="IC Markets",
            login="2000002",
            server="ICMarkets-Live",
            initial_balance=5000.0,
        )
    )
    demo = service.register_account(
        TradingAccountCreate(
            label="Demo",
            account_type=AccountType.demo,
            broker="IC Markets",
            login="3000003",
            server="ICMarkets-Demo",
            initial_balance=10000.0,
        )
    )
    assert live.prop_rules is None
    assert demo.account_type == AccountType.demo


def test_prop_account_requires_rules() -> None:
    with pytest.raises(ValueError):
        TradingAccountCreate(
            label="Prop no rules",
            account_type=AccountType.prop,
            broker="FTMO",
            login="9",
            server="FTMO-Demo",
            initial_balance=100000.0,
        )


def test_login_server_uniqueness(service: AccountRegistryService) -> None:
    service.register_account(_prop_payload())
    with pytest.raises(AccountRegistryError):
        service.register_account(_prop_payload(label="dup"))


def test_same_login_different_server_allowed(service: AccountRegistryService) -> None:
    service.register_account(_prop_payload())
    other = service.register_account(_prop_payload(server="FTMO-Demo2"))
    assert other.server == "FTMO-Demo2"


# -- strategy assignment -----------------------------------------------------


def test_assign_up_to_two_strategies(service: AccountRegistryService) -> None:
    acc = service.register_account(_prop_payload())
    service.assign_strategy(acc.id, StrategyAssignmentCreate(strategy_id="s1", strategy_name="Scalp", allocation_pct=50))
    service.assign_strategy(acc.id, StrategyAssignmentCreate(strategy_id="s2", strategy_name="Swing", allocation_pct=50))
    assignments = service.list_assignments(acc.id)
    assert len(assignments) == 2


def test_max_strategies_enforced(service: AccountRegistryService) -> None:
    acc = service.register_account(_prop_payload())
    service.assign_strategy(acc.id, StrategyAssignmentCreate(strategy_id="s1", strategy_name="A", allocation_pct=30))
    service.assign_strategy(acc.id, StrategyAssignmentCreate(strategy_id="s2", strategy_name="B", allocation_pct=30))
    with pytest.raises(AccountRegistryError, match="maximum"):
        service.assign_strategy(acc.id, StrategyAssignmentCreate(strategy_id="s3", strategy_name="C", allocation_pct=30))


def test_duplicate_strategy_rejected(service: AccountRegistryService) -> None:
    acc = service.register_account(_prop_payload())
    service.assign_strategy(acc.id, StrategyAssignmentCreate(strategy_id="s1", strategy_name="A", allocation_pct=30))
    with pytest.raises(AccountRegistryError, match="already assigned"):
        service.assign_strategy(acc.id, StrategyAssignmentCreate(strategy_id="s1", strategy_name="A", allocation_pct=30))


def test_allocation_over_100_rejected(service: AccountRegistryService) -> None:
    acc = service.register_account(_prop_payload())
    service.assign_strategy(acc.id, StrategyAssignmentCreate(strategy_id="s1", strategy_name="A", allocation_pct=60))
    with pytest.raises(AccountRegistryError, match="exceeds 100"):
        service.assign_strategy(acc.id, StrategyAssignmentCreate(strategy_id="s2", strategy_name="B", allocation_pct=50))


def test_unassign_strategy(service: AccountRegistryService) -> None:
    acc = service.register_account(_prop_payload())
    service.assign_strategy(acc.id, StrategyAssignmentCreate(strategy_id="s1", strategy_name="A", allocation_pct=60))
    service.unassign_strategy(acc.id, "s1")
    assert service.list_assignments(acc.id) == []
    with pytest.raises(AccountRegistryError):
        service.unassign_strategy(acc.id, "s1")


# -- state & compliance ------------------------------------------------------


def test_state_update_and_compliance_math(service: AccountRegistryService) -> None:
    acc = service.register_account(_prop_payload())
    service.update_state(acc.id, AccountStateUpdate(balance=103000, equity=103000, as_of_date="2026-01-01"))
    comp = service.compliance(acc.id)
    assert comp.profit_pct == pytest.approx(3.0)
    assert comp.daily_loss_pct == 0.0
    assert comp.total_drawdown_pct == 0.0
    assert comp.breached is False
    assert comp.profit_target_progress_pct == pytest.approx(30.0)


def test_daily_loss_breach_flags_account(service: AccountRegistryService) -> None:
    acc = service.register_account(_prop_payload())
    updated = service.update_state(acc.id, AccountStateUpdate(balance=94000, equity=94000, as_of_date="2026-01-02"))
    assert updated.status == AccountStatus.breached
    comp = service.compliance(acc.id)
    assert comp.breached is True
    assert any("daily loss" in r for r in comp.breach_reasons)


def test_total_drawdown_breach(service: AccountRegistryService) -> None:
    acc = service.register_account(
        _prop_payload(
            prop_rules=PropFirmRules(max_daily_loss_pct=50.0, max_total_drawdown_pct=10.0, profit_target_pct=10.0)
        )
    )
    updated = service.update_state(acc.id, AccountStateUpdate(balance=89000, equity=89000, as_of_date="2026-01-03"))
    assert updated.status == AccountStatus.breached
    comp = service.compliance(acc.id)
    assert any("total drawdown" in r for r in comp.breach_reasons)


def test_trailing_drawdown_uses_peak_equity(service: AccountRegistryService) -> None:
    acc = service.register_account(
        _prop_payload(
            prop_rules=PropFirmRules(
                max_daily_loss_pct=50.0,
                max_total_drawdown_pct=5.0,
                profit_target_pct=10.0,
                drawdown_type=DrawdownType.trailing,
            )
        )
    )
    service.update_state(acc.id, AccountStateUpdate(balance=110000, equity=110000, as_of_date="2026-01-04"))
    # Drop from a peak of 110k to 108k = 1.8% trailing drawdown (not breached at 5%).
    comp_before = service.compliance(acc.id)
    service.update_state(acc.id, AccountStateUpdate(balance=104000, equity=104000, as_of_date="2026-01-05"))
    comp = service.compliance(acc.id)
    assert comp_before.total_drawdown_pct == 0.0
    # (110000-104000)/110000 = 5.4545% > 5% -> breach
    assert comp.breached is True
    assert comp.peak_equity == 110000


def test_trading_days_counted_distinctly(service: AccountRegistryService) -> None:
    acc = service.register_account(_prop_payload())
    service.update_state(acc.id, AccountStateUpdate(balance=101000, equity=101000, as_of_date="2026-02-01"))
    service.update_state(acc.id, AccountStateUpdate(balance=101500, equity=101500, as_of_date="2026-02-01"))
    service.update_state(acc.id, AccountStateUpdate(balance=102000, equity=102000, as_of_date="2026-02-02"))
    comp = service.compliance(acc.id)
    assert comp.trading_days == 2
    assert comp.min_trading_days_met is False


def test_intraday_update_keeps_day_start(service: AccountRegistryService) -> None:
    acc = service.register_account(_prop_payload())
    service.update_state(acc.id, AccountStateUpdate(balance=100000, equity=99000, as_of_date="2026-03-01"))
    rec = service.get_account(acc.id)
    assert rec.day_start_balance == 100000
    comp = service.compliance(acc.id)
    assert comp.daily_loss_pct == pytest.approx(1.0)


# -- status transitions ------------------------------------------------------


def test_suspend_and_activate(service: AccountRegistryService) -> None:
    acc = service.register_account(_prop_payload())
    assert service.suspend(acc.id).status == AccountStatus.suspended
    assert service.activate(acc.id).status == AccountStatus.active


def test_breached_account_cannot_reactivate(service: AccountRegistryService) -> None:
    acc = service.register_account(_prop_payload())
    service.update_state(acc.id, AccountStateUpdate(balance=94000, equity=94000, as_of_date="2026-04-01"))
    with pytest.raises(AccountRegistryError, match="breached"):
        service.activate(acc.id)


# -- persistence -------------------------------------------------------------


def test_persistence_across_reinit(tmp_path) -> None:
    db = tmp_path / "accounts.db"
    svc1 = AccountRegistryService(db_path=db)
    acc = svc1.register_account(_prop_payload())
    svc1.assign_strategy(acc.id, StrategyAssignmentCreate(strategy_id="s1", strategy_name="A", allocation_pct=40))
    svc2 = AccountRegistryService(db_path=db)
    reloaded = svc2.get_account(acc.id)
    assert reloaded.login == "1000001"
    assert len(svc2.list_assignments(acc.id)) == 1


def test_missing_account_raises(service: AccountRegistryService) -> None:
    import uuid

    with pytest.raises(AccountRegistryError):
        service.get_account(uuid.uuid4())


# -- API surface -------------------------------------------------------------


def test_api_register_and_flow() -> None:
    payload = {
        "label": "FTMO 100k",
        "account_type": "prop",
        "broker": "FTMO",
        "login": "5000005",
        "server": "FTMO-Demo",
        "initial_balance": 100000.0,
        "prop_rules": {"max_daily_loss_pct": 5.0, "max_total_drawdown_pct": 10.0, "profit_target_pct": 10.0},
    }
    resp = client.post("/v1/accounts", json=payload)
    assert resp.status_code == 201, resp.text
    account_id = resp.json()["id"]

    # duplicate login/server -> 409
    assert client.post("/v1/accounts", json=payload).status_code == 409

    # assign strategy
    assign = client.post(
        f"/v1/accounts/{account_id}/strategies",
        json={"strategy_id": "s1", "strategy_name": "Scalp", "allocation_pct": 50},
    )
    assert assign.status_code == 201, assign.text

    # state update + compliance
    assert client.post(f"/v1/accounts/{account_id}/state", json={"balance": 103000, "equity": 103000}).status_code == 200
    comp = client.get(f"/v1/accounts/{account_id}/compliance")
    assert comp.status_code == 200
    assert comp.json()["profit_pct"] == pytest.approx(3.0)

    # list
    assert client.get("/v1/accounts").status_code == 200
    assert len(client.get("/v1/accounts").json()) == 1

    # suspend / activate
    assert client.post(f"/v1/accounts/{account_id}/suspend").json()["status"] == "suspended"
    assert client.post(f"/v1/accounts/{account_id}/activate").json()["status"] == "active"


def test_api_prop_without_rules_rejected() -> None:
    resp = client.post(
        "/v1/accounts",
        json={
            "label": "bad",
            "account_type": "prop",
            "broker": "FTMO",
            "login": "6000006",
            "server": "FTMO-Demo",
            "initial_balance": 100000.0,
        },
    )
    assert resp.status_code == 422
