import pytest

from app.executive_live_rebalancing_strategy_rotation.models import (
    RebalancingAssessmentCreate,
    RebalancingState,
    RotationPolicy,
    StrategyPosition,
)
from app.executive_live_rebalancing_strategy_rotation.service import (
    ExecutiveLiveRebalancingStrategyRotationService,
)


def position(**overrides):
    data = dict(
        strategy_id="ict-xau",
        broker_id="broker-a",
        symbol="XAUUSD",
        current_capital=5000,
        target_capital=4000,
        current_risk_share=0.25,
        performance_score=75,
        stability_score=80,
        drawdown_share=0.04,
        correlation_group="metals",
    )
    data.update(overrides)
    return StrategyPosition(**data)


def payload(**overrides):
    data = dict(
        workspace_id="ws-1",
        source_key="rotation-1",
        actor_id="master-brano",
        owned_live_capital=10000,
        human_approved=True,
        risk_brain_clear=True,
        positions=[
            position(),
            position(
                strategy_id="fx-swing",
                broker_id="broker-b",
                symbol="EURUSD",
                current_capital=3000,
                target_capital=4000,
                performance_score=85,
                stability_score=88,
                correlation_group="fx",
            ),
            position(
                strategy_id="cash-buffer",
                broker_id="broker-b",
                symbol="CASH",
                current_capital=2000,
                target_capital=2000,
                performance_score=90,
                stability_score=95,
                correlation_group="cash",
            ),
        ],
        policy=RotationPolicy(max_rotation_share_per_cycle=0.25),
    )
    data.update(overrides)
    return RebalancingAssessmentCreate(**data)


def test_rotation_ready_moves_capital_to_stronger_strategy():
    service = ExecutiveLiveRebalancingStrategyRotationService()
    result = service.create(payload())
    assert result.state == RebalancingState.rotation_ready
    assert result.approved_rotation_capital > 0
    assert any(line.recommended_change > 0 for line in result.rotation_lines)
    assert all(line.deployable for line in result.rotation_lines if line.recommended_change != 0)


def test_weak_strategy_is_reduced():
    service = ExecutiveLiveRebalancingStrategyRotationService()
    result = service.create(
        payload(
            positions=[
                position(performance_score=30, stability_score=40, target_capital=5000),
                position(strategy_id="cash", symbol="CASH", current_capital=5000, target_capital=5000),
            ]
        )
    )
    assert result.state == RebalancingState.rebalance
    assert result.rotation_lines[0].recommended_change < 0


def test_human_approval_holds_rotation():
    service = ExecutiveLiveRebalancingStrategyRotationService()
    result = service.create(payload(human_approved=False))
    assert result.state == RebalancingState.hold
    assert result.approved_rotation_capital == 0


def test_risk_brain_blocks_rotation():
    service = ExecutiveLiveRebalancingStrategyRotationService()
    result = service.create(payload(risk_brain_clear=False))
    assert result.state == RebalancingState.blocked
    assert result.approved_rotation_capital == 0


def test_workspace_isolation_and_duplicate_protection():
    service = ExecutiveLiveRebalancingStrategyRotationService()
    created = service.create(payload())
    assert service.get(created.id, "other") is None
    with pytest.raises(ValueError):
        service.create(payload())
