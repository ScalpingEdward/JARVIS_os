from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.backtesting_lab.models import BacktestComparisonRequest, BacktestDataset, BacktestJobCreate
from app.backtesting_lab.service import BacktestUnavailable, backtesting_lab_service


def setup_function() -> None:
    backtesting_lab_service.reset()


def job() -> BacktestJobCreate:
    return BacktestJobCreate(strategy_id=uuid4(), strategy_version=1, dataset=BacktestDataset(
        symbol="XAUUSD", timeframe="M15", bars=20_000,
        start=datetime(2024, 1, 1, tzinfo=timezone.utc), end=datetime(2025, 1, 1, tzinfo=timezone.utc)))


def test_a_backtest_without_prices_is_refused_not_invented() -> None:
    with pytest.raises(BacktestUnavailable, match="no price data"):
        backtesting_lab_service.create(job())
    assert backtesting_lab_service.list_all() == []
    assert backtesting_lab_service.status().jobs == 0


def test_the_api_says_503_instead_of_numbers() -> None:
    from app.main import app
    r = TestClient(app).post("/v1/backtesting-lab/jobs", json=job().model_dump(mode="json"))
    assert r.status_code == 503 and "no price data" in r.json()["detail"]


def test_comparison_rejects_unknown_jobs() -> None:
    with pytest.raises(KeyError):
        backtesting_lab_service.compare(BacktestComparisonRequest(job_ids=[uuid4(), uuid4()]))
