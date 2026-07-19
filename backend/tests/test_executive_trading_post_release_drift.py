import pytest

from app.executive_trading_post_release_drift.models import BaselineMetric, DriftDimension, MonitoringInput, MonitoringState
from app.executive_trading_post_release_drift.service import ExecutiveTradingPostReleaseDriftService


def payload(**overrides):
    data = dict(
        workspace_id="ws-1",
        actor_id="ops",
        source_key="release-1",
        symbol="XAUUSD",
        account_profile="funded",
        release_state="reduced_live",
        approved_risk_multiplier=0.5,
        observation_trades=12,
        minimum_observation_trades=10,
        stable_minutes=90,
        minimum_stable_minutes=60,
        metrics=[
            BaselineMetric(name="expectancy", baseline_value=1.0, current_value=1.02, tolerance_percent=10, higher_is_better=True, dimension=DriftDimension.performance),
            BaselineMetric(name="drawdown", baseline_value=2.0, current_value=1.9, tolerance_percent=10, higher_is_better=False, dimension=DriftDimension.risk),
            BaselineMetric(name="latency", baseline_value=100, current_value=95, tolerance_percent=15, higher_is_better=False, dimension=DriftDimension.execution),
        ],
    )
    data.update(overrides)
    return MonitoringInput(**data)


def test_stable_release_can_promote():
    service = ExecutiveTradingPostReleaseDriftService()
    result = service.assess(payload())
    assert result.state == MonitoringState.stable
    assert result.promotion_allowed is True
    assert result.recommended_risk_multiplier == 0.5


def test_warning_drift_reduces_risk():
    service = ExecutiveTradingPostReleaseDriftService()
    item = payload(source_key="release-2", metrics=[BaselineMetric(name="expectancy", baseline_value=1.0, current_value=0.72, tolerance_percent=10, higher_is_better=True, dimension=DriftDimension.performance)])
    result = service.assess(item)
    assert result.state == MonitoringState.reduce
    assert result.recommended_risk_multiplier <= 0.25


def test_critical_risk_drift_blocks():
    service = ExecutiveTradingPostReleaseDriftService()
    item = payload(source_key="release-3", metrics=[BaselineMetric(name="drawdown", baseline_value=2.0, current_value=4.0, tolerance_percent=10, higher_is_better=False, dimension=DriftDimension.risk)])
    result = service.assess(item)
    assert result.state == MonitoringState.blocked
    assert result.regression_required is True
    assert result.recommended_risk_multiplier == 0


def test_recurrent_incident_blocks():
    service = ExecutiveTradingPostReleaseDriftService()
    result = service.assess(payload(source_key="release-4", incident_recurrence_count=2))
    assert result.state == MonitoringState.blocked


def test_duplicate_source_is_rejected():
    service = ExecutiveTradingPostReleaseDriftService()
    service.assess(payload())
    with pytest.raises(ValueError):
        service.assess(payload())


def test_workspace_isolation():
    service = ExecutiveTradingPostReleaseDriftService()
    service.assess(payload())
    service.assess(payload(workspace_id="ws-2", source_key="release-1"))
    assert len(service.list_assessments("ws-1")) == 1
    assert len(service.list_assessments("ws-2")) == 1
