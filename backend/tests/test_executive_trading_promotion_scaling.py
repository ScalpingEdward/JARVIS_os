import pytest

from app.executive_trading_promotion_scaling.models import PromotionInput, PromotionState, ScalingGate
from app.executive_trading_promotion_scaling.service import ExecutiveTradingPromotionScalingService


def ready_payload(**overrides):
    data = dict(
        workspace_id="ws-a",
        actor_id="chief-risk",
        source_key="cycle-1",
        strategy_id="ict-trend-v7",
        current_risk_multiplier=0.25,
        requested_risk_multiplier=0.5,
        current_capital=10000,
        requested_capital=10000,
        promotion_eligible=True,
        overall_health=92,
        risk_stability=90,
        execution_stability=91,
        operational_stability=94,
        evidence_quality=88,
        sample_trades=40,
        minimum_sample_trades=30,
        stable_hours=48,
        minimum_stable_hours=24,
        max_drawdown_percent=2,
        drawdown_limit_percent=5,
        human_approval=True,
        gates=[ScalingGate(name="risk-clearance", passed=True)],
    )
    data.update(overrides)
    return PromotionInput(**data)


def test_promotes_only_one_risk_step():
    service = ExecutiveTradingPromotionScalingService()
    result = service.assess(ready_payload())
    assert result.state == PromotionState.promote_risk
    assert result.approved_risk_multiplier == 0.5
    assert len(result.scaling_plan) == 1


def test_missing_approval_holds_current_allocation():
    service = ExecutiveTradingPromotionScalingService()
    result = service.assess(ready_payload(human_approval=False))
    assert result.state == PromotionState.hold
    assert result.approved_risk_multiplier == 0.25


def test_critical_issue_blocks_scaling():
    service = ExecutiveTradingPromotionScalingService()
    result = service.assess(ready_payload(open_critical_issues=1))
    assert result.state == PromotionState.blocked


def test_symbol_expansion_is_incremental():
    service = ExecutiveTradingPromotionScalingService()
    result = service.assess(ready_payload(requested_risk_multiplier=0.25, current_symbol_count=1, requested_symbol_count=4))
    assert result.state == PromotionState.expand_symbols
    assert result.approved_symbol_count == 2


def test_workspace_isolation_and_duplicate_protection():
    service = ExecutiveTradingPromotionScalingService()
    first = service.assess(ready_payload())
    assert service.get(first.id, "ws-b") is None
    with pytest.raises(ValueError):
        service.assess(ready_payload())
