from uuid import UUID

from .models import (
    ForwardValidationStatus,
    RuleResult,
    ValidationCreate,
    ValidationReport,
    ValidationState,
)


class ForwardValidationService:
    def __init__(self) -> None:
        self._reports: dict[UUID, ValidationReport] = {}

    def status(self) -> ForwardValidationStatus:
        return ForwardValidationStatus()

    def create(self, payload: ValidationCreate) -> ValidationReport:
        initial = payload.account_size
        current = payload.days[-1].ending_balance
        net_profit = round(current - initial, 2)
        profit_pct = round(net_profit / initial * 100, 4)
        total_trades = sum(day.trades for day in payload.days)

        daily_dd_values = [
            max(0.0, (day.starting_balance - day.lowest_equity) / day.starting_balance * 100)
            for day in payload.days
        ]
        max_daily_dd = round(max(daily_dd_values, default=0.0), 4)
        min_equity = min(day.lowest_equity for day in payload.days)
        max_total_dd = round(max(0.0, (initial - min_equity) / initial * 100), 4)

        day_profits = [max(0.0, day.ending_balance - day.starting_balance) for day in payload.days]
        gross_positive = sum(day_profits)
        largest_share = (
            round(max(day_profits) / gross_positive * 100, 4) if gross_positive > 0 else None
        )

        rules = [
            RuleResult(
                rule="profit_target",
                passed=profit_pct >= payload.profit_target_pct,
                actual=profit_pct,
                limit=payload.profit_target_pct,
                message="Profit target reached." if profit_pct >= payload.profit_target_pct else "Profit target not reached.",
            ),
            RuleResult(
                rule="daily_drawdown",
                passed=max_daily_dd <= payload.max_daily_drawdown_pct,
                actual=max_daily_dd,
                limit=payload.max_daily_drawdown_pct,
                message="Daily drawdown within limit." if max_daily_dd <= payload.max_daily_drawdown_pct else "Daily drawdown limit breached.",
            ),
            RuleResult(
                rule="total_drawdown",
                passed=max_total_dd <= payload.max_total_drawdown_pct,
                actual=max_total_dd,
                limit=payload.max_total_drawdown_pct,
                message="Total drawdown within limit." if max_total_dd <= payload.max_total_drawdown_pct else "Maximum drawdown limit breached.",
            ),
            RuleResult(
                rule="minimum_trading_days",
                passed=len(payload.days) >= payload.minimum_trading_days,
                actual=len(payload.days),
                limit=payload.minimum_trading_days,
                message="Minimum trading days completed." if len(payload.days) >= payload.minimum_trading_days else "More trading days are required.",
            ),
        ]
        if payload.maximum_single_day_profit_share_pct is not None:
            rules.append(
                RuleResult(
                    rule="consistency",
                    passed=largest_share is not None and largest_share <= payload.maximum_single_day_profit_share_pct,
                    actual=largest_share,
                    limit=payload.maximum_single_day_profit_share_pct,
                    message="Profit distribution is consistent." if largest_share is not None and largest_share <= payload.maximum_single_day_profit_share_pct else "One trading day contributes too much profit.",
                )
            )

        blockers = [rule.message for rule in rules if not rule.passed]
        hard_failure = any(
            not rule.passed for rule in rules if rule.rule in {"daily_drawdown", "total_drawdown"}
        )
        all_passed = all(rule.passed for rule in rules)
        if hard_failure:
            state = ValidationState.FAILED
        elif all_passed:
            state = ValidationState.PASSED
        elif profit_pct > 0:
            state = ValidationState.IN_PROGRESS
        else:
            state = ValidationState.READY

        recommendation = (
            "MASTER Brano: simulated challenge passed; review the evidence manually before any real account use."
            if state == ValidationState.PASSED
            else "MASTER Brano: keep this strategy in simulation and resolve every blocker before approval."
        )
        report = ValidationReport(
            name=payload.name.strip(),
            account_size=initial,
            state=state,
            current_balance=current,
            net_profit=net_profit,
            profit_pct=profit_pct,
            completed_trading_days=len(payload.days),
            total_trades=total_trades,
            maximum_daily_drawdown_pct=max_daily_dd,
            maximum_total_drawdown_pct=max_total_dd,
            largest_day_profit_share_pct=largest_share,
            rules=rules,
            blockers=blockers,
            recommendation=recommendation,
        )
        self._reports[report.id] = report
        return report

    def list_all(self) -> list[ValidationReport]:
        return sorted(self._reports.values(), key=lambda item: item.created_at, reverse=True)

    def get(self, report_id: UUID) -> ValidationReport | None:
        return self._reports.get(report_id)


forward_validation_service = ForwardValidationService()
