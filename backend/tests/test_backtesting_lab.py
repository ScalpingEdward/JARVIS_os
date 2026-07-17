from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.backtesting_lab.models import (
    BacktestComparisonRequest,
    BacktestDataset,
    BacktestJobCreate,
    CostModel,
    SplitMode,
)
from app.backtesting_lab.service import backtesting_lab_service


def setup_function() -> None:
    backtesting_lab_service.reset()


def dataset(bars: int = 20_000) -> BacktestDataset:
    return BacktestDataset(
        symbol="XAUUSD",
        timeframe="M15",
        bars=bars,
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def test_job_is_human_gated_and_never_executes() -> None:
    job = backtesting_lab_service.create(
        BacktestJobCreate(strategy_id=uuid4(), strategy_version=1, dataset=dataset())
    )
    assert job.owner_name == "MASTER Brano"
    assert job.human_approval_required is True
    assert job.automatic_execution is False
    assert job.automatic_order_execution is False


def test_costs_reduce_backtest_profit() -> None:
    clean = backtesting_lab_service.create(
        BacktestJobCreate(strategy_id=uuid4(), strategy_version=1, dataset=dataset())
    )
    costly = backtesting_lab_service.create(
        BacktestJobCreate(
            strategy_id=uuid4(),
            strategy_version=1,
            dataset=dataset(),
            costs=CostModel(spread_points=20, slippage_points=10, commission_per_lot=7),
        )
    )
    assert costly.metrics.net_profit_pct < clean.metrics.net_profit_pct


def test_walk_forward_improves_stability_and_removes_warning() -> None:
    full = backtesting_lab_service.create(
        BacktestJobCreate(strategy_id=uuid4(), strategy_version=1, dataset=dataset())
    )
    walk = backtesting_lab_service.create(
        BacktestJobCreate(
            strategy_id=uuid4(),
            strategy_version=1,
            dataset=dataset(),
            split_mode=SplitMode.walk_forward,
        )
    )
    assert walk.metrics.stability_score > full.metrics.stability_score
    assert not any("walk-forward" in warning.lower() for warning in walk.warnings)


def test_comparison_ranks_jobs_and_stays_advisory() -> None:
    conservative = backtesting_lab_service.create(
        BacktestJobCreate(strategy_id=uuid4(), strategy_version=1, dataset=dataset(), risk_per_trade_pct=0.5)
    )
    aggressive = backtesting_lab_service.create(
        BacktestJobCreate(strategy_id=uuid4(), strategy_version=1, dataset=dataset(), risk_per_trade_pct=4.0)
    )
    result = backtesting_lab_service.compare(
        BacktestComparisonRequest(job_ids=[conservative.id, aggressive.id])
    )
    assert result.best_job_id == conservative.id
    assert result.human_approval_required is True
    assert result.automatic_execution is False


def test_comparison_rejects_missing_job() -> None:
    existing = backtesting_lab_service.create(
        BacktestJobCreate(strategy_id=uuid4(), strategy_version=1, dataset=dataset())
    )
    with pytest.raises(KeyError):
        backtesting_lab_service.compare(
            BacktestComparisonRequest(job_ids=[existing.id, uuid4()])
        )
