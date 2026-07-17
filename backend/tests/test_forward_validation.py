import pytest
from pydantic import ValidationError

from app.forward_validation.models import TradingDay, ValidationCreate, ValidationState
from app.forward_validation.service import ForwardValidationService


def day(number: int, start: float, end: float, low: float, trades: int = 1) -> TradingDay:
    return TradingDay(
        day=number,
        starting_balance=start,
        ending_balance=end,
        lowest_equity=low,
        trades=trades,
    )


def payload(**overrides) -> ValidationCreate:
    values = {
        "name": "FTMO-style forward validation",
        "account_size": 10000,
        "profit_target_pct": 10,
        "max_daily_drawdown_pct": 5,
        "max_total_drawdown_pct": 10,
        "minimum_trading_days": 4,
        "days": [
            day(1, 10000, 10300, 9900, 2),
            day(2, 10300, 10600, 10200, 2),
            day(3, 10600, 10900, 10500, 2),
            day(4, 10900, 11100, 10800, 2),
        ],
    }
    values.update(overrides)
    return ValidationCreate(**values)


def test_passing_forward_validation_report() -> None:
    service = ForwardValidationService()
    report = service.create(payload())
    assert report.state == ValidationState.PASSED
    assert report.profit_pct == 11
    assert report.completed_trading_days == 4
    assert report.total_trades == 8
    assert report.blockers == []


def test_daily_drawdown_breach_fails_report() -> None:
    service = ForwardValidationService()
    report = service.create(
        payload(days=[
            day(1, 10000, 9600, 9400),
            day(2, 9600, 9700, 9500),
            day(3, 9700, 9800, 9600),
            day(4, 9800, 9900, 9700),
        ])
    )
    assert report.state == ValidationState.FAILED
    assert any("Daily drawdown" in blocker for blocker in report.blockers)


def test_incomplete_target_remains_in_progress() -> None:
    service = ForwardValidationService()
    report = service.create(
        payload(days=[
            day(1, 10000, 10100, 9900),
            day(2, 10100, 10200, 10000),
            day(3, 10200, 10300, 10100),
            day(4, 10300, 10400, 10200),
        ])
    )
    assert report.state == ValidationState.IN_PROGRESS
    assert "Profit target not reached." in report.blockers


def test_consistency_rule_detects_single_day_concentration() -> None:
    service = ForwardValidationService()
    report = service.create(
        payload(
            maximum_single_day_profit_share_pct=40,
            days=[
                day(1, 10000, 10900, 9950),
                day(2, 10900, 11000, 10800),
                day(3, 11000, 11100, 10900),
                day(4, 11100, 11200, 11000),
            ],
        )
    )
    assert report.state == ValidationState.IN_PROGRESS
    assert any(rule.rule == "consistency" and not rule.passed for rule in report.rules)


def test_reports_can_be_listed_and_retrieved() -> None:
    service = ForwardValidationService()
    report = service.create(payload())
    assert service.get(report.id) == report
    assert service.list_all() == [report]


def test_automatic_execution_and_missing_approval_are_rejected() -> None:
    with pytest.raises(ValidationError):
        payload(automatic_execution=True)
    with pytest.raises(ValidationError):
        payload(human_approved=False)
