import pytest
from pydantic import ValidationError

from app.strategy_builder.models import RiskConfig, RuleKind, StrategyCreate, StrategyRule, StrategyStatus
from app.strategy_builder.service import strategy_builder_service


def setup_function() -> None:
    strategy_builder_service.reset()


def valid_payload() -> StrategyCreate:
    return StrategyCreate(
        name="XAUUSD London Sweep",
        description="Advisory ICT strategy with confirmation and protected risk.",
        symbols=["XAUUSD"],
        rules=[
            StrategyRule(kind=RuleKind.filter, name="London session", expression="session == london"),
            StrategyRule(kind=RuleKind.entry, name="Liquidity sweep", expression="sweep and bullish_bos", timeframe="M15"),
            StrategyRule(kind=RuleKind.exit, name="Invalidation", expression="close_below_order_block", timeframe="M15"),
        ],
        risk=RiskConfig(risk_per_trade_pct=1.0, max_daily_risk_pct=2.0, minimum_rr=3.0),
    )


def test_strategy_validates_and_is_backtest_ready() -> None:
    record = strategy_builder_service.create(valid_payload())
    validated = strategy_builder_service.validate(record.id)
    assert validated is not None
    assert validated.status == StrategyStatus.validated
    assert validated.backtest_ready is True
    assert validated.requires_human_approval is True
    assert validated.automatic_execution is False


def test_missing_filter_creates_warning_but_remains_ready() -> None:
    payload = valid_payload()
    payload.rules = [rule for rule in payload.rules if rule.kind != RuleKind.filter]
    record = strategy_builder_service.create(payload)
    validated = strategy_builder_service.validate(record.id)
    assert validated is not None
    assert validated.backtest_ready is True
    assert any(issue.code == "no_market_filter" for issue in validated.issues)


def test_unsafe_risk_blocks_backtest_readiness() -> None:
    payload = valid_payload()
    payload.risk.risk_per_trade_pct = 3.0
    payload.risk.max_daily_risk_pct = 2.0
    record = strategy_builder_service.create(payload)
    validated = strategy_builder_service.validate(record.id)
    assert validated is not None
    assert validated.status == StrategyStatus.invalid
    assert validated.backtest_ready is False


def test_automatic_execution_is_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyCreate(
            name="Unsafe Strategy",
            description="This configuration must be rejected.",
            symbols=["XAUUSD"],
            rules=[
                StrategyRule(kind=RuleKind.entry, name="Entry rule", expression="signal == true"),
                StrategyRule(kind=RuleKind.exit, name="Exit rule", expression="invalidated == true"),
            ],
            risk=RiskConfig(automatic_execution=True),
        )


def test_status_counts_strategies() -> None:
    record = strategy_builder_service.create(valid_payload())
    strategy_builder_service.validate(record.id)
    status = strategy_builder_service.status()
    assert status.owner_name == "MASTER Brano"
    assert status.strategies == 1
    assert status.validated == 1
    assert status.automatic_order_execution is False
