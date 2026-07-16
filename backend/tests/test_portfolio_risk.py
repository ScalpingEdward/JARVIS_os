from app.portfolio_risk.models import AccountSnapshotCreate, AccountType, PositionSnapshot, RiskState, StressScenario
from app.portfolio_risk.service import portfolio_risk_service


def setup_function() -> None:
    portfolio_risk_service.reset()


def test_portfolio_report_tracks_drawdown_and_requires_human_approval() -> None:
    account = portfolio_risk_service.add_snapshot(
        AccountSnapshotCreate(
            account_name="FTMO 100K",
            account_type=AccountType.funded,
            provider="FTMO",
            balance=100000,
            equity=96500,
            day_start_balance=100000,
            initial_balance=100000,
            daily_drawdown_limit_pct=5,
            max_drawdown_limit_pct=10,
            positions=[PositionSnapshot(symbol="XAUUSD", direction="long", notional=50000, strategy="ICT")],
        )
    )
    assert account.daily_drawdown_pct == 3.5
    assert account.risk_state == RiskState.warning
    report = portfolio_risk_service.report()
    assert report.owner_name == "MASTER Brano"
    assert report.requires_human_approval is True
    assert report.automatic_order_execution is False
    assert report.symbol_exposure["XAUUSD"] == 50000


def test_concentration_and_stress_scenario_raise_risk() -> None:
    portfolio_risk_service.add_snapshot(
        AccountSnapshotCreate(
            account_name="Live Account",
            account_type=AccountType.live,
            provider="Broker",
            balance=20000,
            equity=20000,
            day_start_balance=20000,
            initial_balance=20000,
            positions=[PositionSnapshot(symbol="XAUUSD", direction="long", notional=20000, strategy="Grid")],
        )
    )
    report = portfolio_risk_service.report()
    assert report.concentration_pct == 100
    assert report.portfolio_risk_state == RiskState.warning
    result = portfolio_risk_service.stress(StressScenario(name="Gold shock", symbol_shocks_pct={"XAUUSD": -12}))
    assert result.projected_pnl == -2400
    assert result.projected_drawdown_pct == 12
    assert result.risk_state == RiskState.blocked
    assert result.automatic_execution is False


def test_breached_account_is_blocked() -> None:
    account = portfolio_risk_service.add_snapshot(
        AccountSnapshotCreate(
            account_name="Funded 10K",
            account_type=AccountType.funded,
            provider="Prop Firm",
            balance=10000,
            equity=9400,
            day_start_balance=10000,
            initial_balance=10000,
            daily_drawdown_limit_pct=5,
            max_drawdown_limit_pct=10,
        )
    )
    assert account.risk_state == RiskState.blocked
