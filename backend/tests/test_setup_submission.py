"""Tests for the setup-submission bridge (strategy output -> approval gate)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.accounts.models import (
    AccountType,
    StrategyAssignmentCreate,
    TradingAccountCreate,
)
from app.accounts.service import AccountRegistryService, account_registry_service
from app.main import app
from app.setup_submission.models import SetupSubmissionRequest
from app.setup_submission.service import SetupSubmissionService, setup_submission_service
from app.strategies.models import (
    FairValueGap,
    HTFBias,
    MarketSnapshot,
    OrderBlock,
    OrderBlockType,
    StructureLevel,
)

client = TestClient(app)


# -- snapshot builders -------------------------------------------------------


def _both_setups_snapshot(symbol: str = "EURUSD") -> MarketSnapshot:
    """A long snapshot for which both registered strategies produce a setup."""
    return MarketSnapshot(
        symbol=symbol,
        current_price=1.10000,
        bid=1.09995,
        ask=1.10005,
        spread=0.00010,
        htf_bias=HTFBias.bullish,
        session="london",
        order_blocks=[
            OrderBlock(type=OrderBlockType.bullish, high=1.10010, low=1.09990, open=1.09990, close=1.10000)
        ],
        fvgs=[FairValueGap(side="bullish", top=1.10020, bottom=1.09980)],
        structure_levels=[
            StructureLevel(level=1.09900, type="low", strength=3),
            StructureLevel(level=1.10500, type="high", strength=4),
        ],
    )


def _no_setup_snapshot(symbol: str = "EURUSD") -> MarketSnapshot:
    """A neutral, empty snapshot for which no strategy produces a setup."""
    return MarketSnapshot(
        symbol=symbol,
        current_price=1.10000,
        bid=1.09995,
        ask=1.10005,
        spread=0.00010,
        htf_bias=HTFBias.neutral,
        session="off",
    )


# -- registry helpers --------------------------------------------------------

_LOGIN_SEQ = [10_000_000]


def _next_login() -> str:
    _LOGIN_SEQ[0] += 1
    return str(_LOGIN_SEQ[0])


def _register_account(registry: AccountRegistryService, *, strategies: list[str]) -> UUID:
    """Register a demo account and assign the given strategies (enabled)."""
    login = _next_login()
    account = registry.register_account(
        TradingAccountCreate(
            label=f"Demo {login}",
            account_type=AccountType.demo,
            broker="TestBroker",
            login=login,
            server="Test-Server",
            currency="USD",
            initial_balance=100000.0,
            max_strategies=max(2, len(strategies)),
        )
    )
    alloc = 100.0 / max(1, len(strategies))
    for sid in strategies:
        registry.assign_strategy(
            account.id,
            StrategyAssignmentCreate(
                strategy_id=sid,
                strategy_name=sid,
                allocation_pct=alloc,
                enabled=True,
            ),
        )
    return account.id


@pytest.fixture()
def registry(tmp_path) -> AccountRegistryService:
    return AccountRegistryService(db_path=tmp_path / "accounts.db")


@pytest.fixture()
def service(registry: AccountRegistryService) -> SetupSubmissionService:
    return SetupSubmissionService(account_registry=registry)


def setup_function() -> None:
    # Reset the shared singletons used by the API-level tests.
    account_registry_service.reset()
    setup_submission_service.reset()


# -- service-level tests -----------------------------------------------------


def test_submit_zero_accounts_yields_zero(service: SetupSubmissionService) -> None:
    report = service.submit(SetupSubmissionRequest(snapshot=_both_setups_snapshot()))
    assert report.total_accounts_evaluated == 0
    assert report.total_executable_setups == 0
    assert report.total_submitted == 0
    assert report.submitted_setups == []
    assert report.skipped_reason is not None


def test_submit_one_account_one_strategy(
    service: SetupSubmissionService, registry: AccountRegistryService
) -> None:
    account_id = _register_account(registry, strategies=["scalping_3tp"])
    snapshot = _both_setups_snapshot()
    report = service.submit(SetupSubmissionRequest(snapshot=snapshot))

    assert report.total_accounts_evaluated == 1
    assert report.total_executable_setups == 1
    assert report.total_submitted == 1
    setup = report.submitted_setups[0]
    assert setup.account_id == account_id
    assert setup.strategy_id == "scalping_3tp"
    assert setup.symbol == "EURUSD"
    assert setup.entry_price == snapshot.ask  # scalping long enters at ask
    assert setup.stop_loss < setup.entry_price
    assert len(setup.take_profits) == 3
    assert setup.risk_reward > 0
    assert 0 <= setup.confidence <= 100
    assert isinstance(setup.approval_request_id, UUID)


def test_submit_one_account_two_strategies(
    service: SetupSubmissionService, registry: AccountRegistryService
) -> None:
    _register_account(registry, strategies=["scalping_3tp", "ict_silver_bullet"])
    report = service.submit(SetupSubmissionRequest(snapshot=_both_setups_snapshot()))
    assert report.total_submitted == 2
    strategy_ids = {s.strategy_id for s in report.submitted_setups}
    assert strategy_ids == {"scalping_3tp", "ict_silver_bullet"}


def test_submit_multiple_accounts(
    service: SetupSubmissionService, registry: AccountRegistryService
) -> None:
    _register_account(registry, strategies=["scalping_3tp"])
    _register_account(registry, strategies=["scalping_3tp"])
    _register_account(registry, strategies=["scalping_3tp", "ict_silver_bullet"])
    report = service.submit(SetupSubmissionRequest(snapshot=_both_setups_snapshot()))
    assert report.total_accounts_evaluated == 3
    assert report.total_submitted == 4  # 1 + 1 + 2


def test_submit_breached_account_yields_zero(
    service: SetupSubmissionService, registry: AccountRegistryService
) -> None:
    from app.accounts.models import AccountStatus

    account_id = _register_account(registry, strategies=["scalping_3tp"])
    registry._set_status(account_id, AccountStatus.breached, "test-breach")
    report = service.submit(SetupSubmissionRequest(snapshot=_both_setups_snapshot()))
    assert report.total_accounts_evaluated == 1  # evaluated but not executable
    assert report.total_executable_setups == 0
    assert report.total_submitted == 0


def test_submit_suspended_account_yields_zero(
    service: SetupSubmissionService, registry: AccountRegistryService
) -> None:
    account_id = _register_account(registry, strategies=["scalping_3tp"])
    registry.suspend(account_id)
    report = service.submit(SetupSubmissionRequest(snapshot=_both_setups_snapshot()))
    assert report.total_executable_setups == 0
    assert report.total_submitted == 0


def test_submit_no_setup_snapshot_yields_zero(
    service: SetupSubmissionService, registry: AccountRegistryService
) -> None:
    _register_account(registry, strategies=["scalping_3tp", "ict_silver_bullet"])
    report = service.submit(SetupSubmissionRequest(snapshot=_no_setup_snapshot()))
    assert report.total_accounts_evaluated == 1
    assert report.total_executable_setups == 0
    assert report.total_submitted == 0
    assert report.skipped_reason is not None


def test_each_submitted_setup_has_unique_approval_id(
    service: SetupSubmissionService, registry: AccountRegistryService
) -> None:
    _register_account(registry, strategies=["scalping_3tp", "ict_silver_bullet"])
    _register_account(registry, strategies=["scalping_3tp", "ict_silver_bullet"])
    report = service.submit(SetupSubmissionRequest(snapshot=_both_setups_snapshot()))
    ids = [s.approval_request_id for s in report.submitted_setups]
    assert len(ids) == 4
    assert len(set(ids)) == 4  # all unique


def test_account_ids_filter(
    service: SetupSubmissionService, registry: AccountRegistryService
) -> None:
    keep = _register_account(registry, strategies=["scalping_3tp"])
    _register_account(registry, strategies=["scalping_3tp"])
    report = service.submit(
        SetupSubmissionRequest(snapshot=_both_setups_snapshot(), account_ids=[keep])
    )
    assert report.total_accounts_evaluated == 1
    assert report.total_submitted == 1
    assert report.submitted_setups[0].account_id == keep


def test_get_pending_count_matches_submissions(
    service: SetupSubmissionService, registry: AccountRegistryService
) -> None:
    _register_account(registry, strategies=["scalping_3tp", "ict_silver_bullet"])
    report = service.submit(SetupSubmissionRequest(snapshot=_both_setups_snapshot()))
    pending = service.get_pending_approvals()
    assert len(pending) == report.total_submitted == 2


def test_get_single_pending_by_id(
    service: SetupSubmissionService, registry: AccountRegistryService
) -> None:
    _register_account(registry, strategies=["scalping_3tp"])
    report = service.submit(SetupSubmissionRequest(snapshot=_both_setups_snapshot()))
    approval_id = report.submitted_setups[0].approval_request_id
    fetched = service.get_approval(approval_id)
    assert fetched is not None
    assert fetched.approval_request_id == approval_id


def test_get_unknown_id_returns_none(service: SetupSubmissionService) -> None:
    assert service.get_approval(uuid4()) is None


def test_multiple_submits_are_independent(
    service: SetupSubmissionService, registry: AccountRegistryService
) -> None:
    _register_account(registry, strategies=["scalping_3tp"])
    snapshot = _both_setups_snapshot()
    report1 = service.submit(SetupSubmissionRequest(snapshot=snapshot))
    report2 = service.submit(SetupSubmissionRequest(snapshot=snapshot))
    assert report1.total_submitted == 1
    assert report2.total_submitted == 1
    # fresh approval ids each time; pending accumulates independently
    assert (
        report1.submitted_setups[0].approval_request_id
        != report2.submitted_setups[0].approval_request_id
    )
    assert len(service.get_pending_approvals()) == 2


def test_symbol_mismatch_rejected() -> None:
    with pytest.raises(ValueError):
        SetupSubmissionRequest(snapshot=_both_setups_snapshot("EURUSD"), symbol="GBPUSD")


# -- API-level tests (use shared singletons) ---------------------------------


def test_api_submit_returns_report_shape() -> None:
    _register_account(account_registry_service, strategies=["scalping_3tp"])
    body = {"snapshot": _both_setups_snapshot().model_dump(mode="json")}
    resp = client.post("/v1/setup-submission/submit", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert set(
        {
            "symbol",
            "total_accounts_evaluated",
            "total_executable_setups",
            "total_submitted",
            "submitted_setups",
            "skipped_reason",
        }
    ).issubset(data.keys())
    assert data["symbol"] == "EURUSD"
    assert data["total_submitted"] == 1
    assert len(data["submitted_setups"]) == 1
    assert "approval_request_id" in data["submitted_setups"][0]


def test_api_pending_list_matches() -> None:
    _register_account(account_registry_service, strategies=["scalping_3tp", "ict_silver_bullet"])
    body = {"snapshot": _both_setups_snapshot().model_dump(mode="json")}
    client.post("/v1/setup-submission/submit", json=body)
    resp = client.get("/v1/setup-submission/pending")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_api_get_single_pending() -> None:
    _register_account(account_registry_service, strategies=["scalping_3tp"])
    body = {"snapshot": _both_setups_snapshot().model_dump(mode="json")}
    submit_resp = client.post("/v1/setup-submission/submit", json=body)
    approval_id = submit_resp.json()["submitted_setups"][0]["approval_request_id"]
    resp = client.get(f"/v1/setup-submission/pending/{approval_id}")
    assert resp.status_code == 200
    assert resp.json()["approval_request_id"] == approval_id


def test_api_get_unknown_pending_returns_404() -> None:
    resp = client.get(f"/v1/setup-submission/pending/{uuid4()}")
    assert resp.status_code == 404
