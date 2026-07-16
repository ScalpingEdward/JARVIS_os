from app.capital_allocation.models import (
    AllocationMode,
    AllocationRequest,
    AllocationTarget,
    AllocationTargetType,
    RebalanceRequest,
)
from app.capital_allocation.service import capital_allocation_service


def setup_function() -> None:
    capital_allocation_service.reset()


def test_plan_keeps_reserve_and_is_human_gated() -> None:
    plan = capital_allocation_service.create_plan(
        AllocationRequest(
            capital=100000,
            reserve_weight=0.2,
            mode=AllocationMode.balanced,
            targets=[
                AllocationTarget(
                    name="FTMO Gold",
                    target_type=AllocationTargetType.account,
                    current_weight=0.4,
                    expected_return=0.16,
                    volatility=0.25,
                    drawdown=0.03,
                    confidence=0.85,
                ),
                AllocationTarget(
                    name="Grid Live",
                    target_type=AllocationTargetType.strategy,
                    current_weight=0.4,
                    expected_return=0.22,
                    volatility=0.7,
                    drawdown=0.12,
                    confidence=0.55,
                ),
            ],
        )
    )
    assert plan.owner_name == "MASTER Brano"
    assert plan.reserve_capital == 20000
    assert plan.automatic_execution is False
    assert plan.automatic_order_execution is False
    assert plan.requires_human_approval is True
    assert any("high drawdown" in warning for warning in plan.warnings)


def test_high_quality_target_receives_more_weight() -> None:
    plan = capital_allocation_service.create_plan(
        AllocationRequest(
            capital=50000,
            targets=[
                AllocationTarget(
                    name="High Quality",
                    target_type=AllocationTargetType.strategy,
                    current_weight=0.2,
                    expected_return=0.2,
                    volatility=0.15,
                    confidence=0.9,
                ),
                AllocationTarget(
                    name="Low Quality",
                    target_type=AllocationTargetType.strategy,
                    current_weight=0.2,
                    expected_return=0.05,
                    volatility=0.6,
                    confidence=0.4,
                ),
            ],
        )
    )
    assert plan.lines[0].name == "High Quality"
    assert plan.lines[0].recommended_weight > plan.lines[1].recommended_weight


def test_rebalance_is_advisory_only() -> None:
    plan = capital_allocation_service.create_plan(
        AllocationRequest(
            capital=10000,
            targets=[
                AllocationTarget(
                    name="Gold Account",
                    target_type=AllocationTargetType.account,
                    current_weight=0.1,
                    expected_return=0.15,
                    confidence=0.8,
                )
            ],
        )
    )
    report = capital_allocation_service.rebalance(RebalanceRequest(plan_id=plan.id, drift_threshold=0.01))
    assert report.requires_human_approval is True
    assert report.automatic_execution is False
    assert report.items
