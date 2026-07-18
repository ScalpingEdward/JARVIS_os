import pytest

from app.executive_performance.models import KPI, MeasurementUpdate, PerformanceRisk, PerformanceStatus, ScorecardCreate
from app.executive_performance.service import ExecutivePerformanceService


def payload(workspace_id: str = "ws-a") -> ScorecardCreate:
    return ScorecardCreate(
        workspace_id=workspace_id,
        owner_id="owner",
        title="FY performance",
        review_period="2026-Q3",
        kpis=[
            KPI(key="revenue", name="Revenue", target=120, current=105, baseline=80, weight=60, owner_id="commercial", objective_key="growth"),
            KPI(key="delivery", name="Delivery reliability", target=95, current=82, baseline=70, weight=40, owner_id="operations", objective_key="quality"),
        ],
        risks=[PerformanceRisk(key="capacity", title="Capacity pressure", probability=80, impact=70, mitigation="Add governed capacity")],
    )


def test_analysis_builds_weighted_score_forecast_alerts_and_recommendations() -> None:
    service = ExecutivePerformanceService()
    record = service.create(payload())
    analyzed = service.analyze(record.id, "ws-a", "analyst")
    assert analyzed.analysis is not None
    assert analyzed.analysis.overall_score > 0
    assert analyzed.analysis.forecast_score <= analyzed.analysis.overall_score
    assert analyzed.analysis.alignment_score == 100
    assert analyzed.analysis.alerts
    assert analyzed.analysis.recommendations
    assert analyzed.analysis.autonomous_actions_enabled is False


def test_measurement_update_resets_analysis_and_reanalyzes() -> None:
    service = ExecutivePerformanceService()
    record = service.create(payload())
    service.analyze(record.id, "ws-a", "analyst")
    updated = service.update_measurements(record.id, "ws-a", MeasurementUpdate(actor_id="operator", values={"delivery": 96}))
    assert updated.analysis is None
    assert updated.status == PerformanceStatus.draft
    analyzed = service.analyze(record.id, "ws-a", "analyst")
    assert next(item for item in analyzed.kpis if item.key == "delivery").current == 96


def test_workspace_isolation_duplicates_status_and_audit() -> None:
    service = ExecutivePerformanceService()
    record = service.create(payload())
    assert service.get(record.id, "ws-b") is None
    assert service.list_scorecards("ws-b") == []
    with pytest.raises(ValueError):
        service.create(payload())
    service.analyze(record.id, "ws-a", "analyst")
    status = service.status("ws-a")
    assert status.version == "18.4"
    assert status.scorecards == 1
    assert status.analyzed_scorecards == 1
    assert status.autonomous_actions_enabled is False
    assert len(service.audit_records("ws-a")) == 2
    assert service.audit_records("ws-b") == []


def test_invalid_weights_unknown_measurements_and_missing_records_are_rejected() -> None:
    with pytest.raises(ValueError):
        ScorecardCreate(workspace_id="ws", owner_id="owner", title="bad", review_period="Q", kpis=[KPI(key="x", name="X", target=1, current=0, weight=90, owner_id="o")])
    service = ExecutivePerformanceService()
    record = service.create(payload())
    with pytest.raises(ValueError):
        service.update_measurements(record.id, "ws-a", MeasurementUpdate(actor_id="operator", values={"unknown": 1}))
    with pytest.raises(KeyError):
        service.analyze(record.id, "ws-b", "analyst")
