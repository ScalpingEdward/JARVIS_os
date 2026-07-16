from uuid import UUID

from .models import (
    AccountSnapshot,
    AccountSnapshotCreate,
    PortfolioReport,
    PortfolioRiskStatus,
    RiskState,
    StressResult,
    StressScenario,
)


class PortfolioRiskService:
    def __init__(self) -> None:
        self._accounts: dict[UUID, AccountSnapshot] = {}

    def reset(self) -> None:
        self._accounts.clear()

    def status(self) -> PortfolioRiskStatus:
        return PortfolioRiskStatus(account_count=len(self._accounts))

    def add_snapshot(self, payload: AccountSnapshotCreate) -> AccountSnapshot:
        daily_dd = max(0.0, (payload.day_start_balance - payload.equity) / payload.day_start_balance * 100)
        total_dd = max(0.0, (payload.initial_balance - payload.equity) / payload.initial_balance * 100)
        state = self._state(daily_dd, total_dd, payload.daily_drawdown_limit_pct, payload.max_drawdown_limit_pct)
        record = AccountSnapshot(
            **payload.model_dump(),
            daily_drawdown_pct=round(daily_dd, 4),
            total_drawdown_pct=round(total_dd, 4),
            risk_state=state,
        )
        self._accounts[record.id] = record
        return record

    def list_accounts(self) -> list[AccountSnapshot]:
        return sorted(self._accounts.values(), key=lambda item: item.captured_at, reverse=True)

    def get_account(self, account_id: UUID) -> AccountSnapshot | None:
        return self._accounts.get(account_id)

    def report(self) -> PortfolioReport:
        accounts = self.list_accounts()
        total_balance = sum(item.balance for item in accounts)
        total_equity = sum(item.equity for item in accounts)
        symbol_exposure: dict[str, float] = {}
        strategy_exposure: dict[str, float] = {}
        for account in accounts:
            for position in account.positions:
                symbol_exposure[position.symbol] = symbol_exposure.get(position.symbol, 0.0) + position.notional
                strategy_exposure[position.strategy] = strategy_exposure.get(position.strategy, 0.0) + position.notional
        gross = sum(symbol_exposure.values())
        concentration = (max(symbol_exposure.values()) / gross * 100) if gross and symbol_exposure else 0.0
        states = {item.risk_state for item in accounts}
        state = RiskState.blocked if RiskState.blocked in states else RiskState.critical if RiskState.critical in states else RiskState.warning if RiskState.warning in states or concentration >= 60 else RiskState.normal
        warnings: list[str] = []
        if concentration >= 60:
            warnings.append(f"Concentration risk: {concentration:.1f}% in one symbol")
        for account in accounts:
            if account.risk_state != RiskState.normal:
                warnings.append(f"{account.account_name}: {account.risk_state.value} drawdown state")
        recommendations = ["Keep all execution human-approved."]
        if concentration >= 60:
            recommendations.append("Reduce correlated or concentrated exposure before adding risk.")
        if state in {RiskState.critical, RiskState.blocked}:
            recommendations.append("Block new exposure and review funded-account limits.")
        return PortfolioReport(
            accounts=accounts,
            total_balance=round(total_balance, 2),
            total_equity=round(total_equity, 2),
            floating_pnl=round(total_equity - total_balance, 2),
            gross_exposure=round(gross, 2),
            symbol_exposure={key: round(value, 2) for key, value in symbol_exposure.items()},
            strategy_exposure={key: round(value, 2) for key, value in strategy_exposure.items()},
            concentration_pct=round(concentration, 2),
            portfolio_risk_state=state,
            warnings=warnings,
            recommendations=recommendations,
        )

    def stress(self, scenario: StressScenario) -> StressResult:
        report = self.report()
        projected_pnl = 0.0
        for symbol, exposure in report.symbol_exposure.items():
            projected_pnl += exposure * scenario.symbol_shocks_pct.get(symbol, 0.0) / 100
        projected_equity = report.total_equity + projected_pnl
        drawdown = max(0.0, (report.total_balance - projected_equity) / report.total_balance * 100) if report.total_balance else 0.0
        state = RiskState.blocked if drawdown >= 10 else RiskState.critical if drawdown >= 7.5 else RiskState.warning if drawdown >= 4 else RiskState.normal
        warnings = ["Stress loss approaches or exceeds portfolio tolerance."] if state != RiskState.normal else []
        return StressResult(
            scenario=scenario.name,
            projected_pnl=round(projected_pnl, 2),
            projected_equity=round(projected_equity, 2),
            projected_drawdown_pct=round(drawdown, 4),
            risk_state=state,
            warnings=warnings,
        )

    @staticmethod
    def _state(daily_dd: float, total_dd: float, daily_limit: float, max_limit: float) -> RiskState:
        if daily_dd >= daily_limit or total_dd >= max_limit:
            return RiskState.blocked
        if daily_dd >= daily_limit * 0.9 or total_dd >= max_limit * 0.9:
            return RiskState.critical
        if daily_dd >= daily_limit * 0.7 or total_dd >= max_limit * 0.7:
            return RiskState.warning
        return RiskState.normal


portfolio_risk_service = PortfolioRiskService()
