import pytest

from app.executive_operations.models import HealthState, ModuleSignal, OperationsSnapshotCreate
from app.executive_operations.service import ExecutiveOperationsService


def payload(workspace_id: str = "workspace-a") -> OperationsSnapshotCreate:
    return OperationsSnapshotCreate(
        workspace_id=workspace_id,
        owner_id="owner-1",
        title="Executive daily operations",
        signals=[
            ModuleSignal(module="jarvis-core", health=HealthState.healthy, readiness_score=92, open_items=4, blocked_items=0, pending_approvals=1, utilization_percent=70, risk_score=20, kpis={"success_rate": 94}, dependency_modules=[]),
            ModuleSignal(module="mission-orchestration", health=HealthState.degraded, readiness_score=68, open_items=8, blocked_items=2, pending_approvals=2, utilization_percent=94, risk_score=58, kpis={"success_rate": 82}, dependency_modules=["execution-governance"]),
            ModuleSignal(module="execution-governance", health=HealthState.critical, readiness_score=35, open_items=5, blocked_items=5, pending_approvals=3, utilization_percent=80, risk_score=84, kpis={"success_rate": 70}, dependency_modules=[]),
        ],
    )


def test_analysis_builds_dashboard_health_alerts_and_heatmap():
    service = ExecutiveOperationsService()
    record = service.create(payload())
    analyzed = service.analyze(record.id, "workspace-a", "analyst-1")

    assert analyzed.analysis is not None
    assert analyzed.analysis.overall_health == HealthState.critical
    assert analyzed.analysis.alerts
    assert len(analyzed.analysis.risk_heatmap) == 3
    assert analyzed.analysis.aggregated_kpis["success_rate"] == 82.0
    assert analyzed.analysis.autonomous_actions_enabled is False


def test_dependency_graph_marks_critical_dependency_as_blocked():
    service = ExecutiveOperationsService()
    record = service.create(payload())
    analyzed = service.analyze(record.id, "workspace-a", "analyst-1")

    edge = analyzed.analysis.dependency_graph[0]
    assert edge.source_module == "mission-orchestration"
    assert edge.target_module == "execution-governance"
    assert edge.blocked is True


def test_status_and_workspace_isolation():
    service = ExecutiveOperationsService()
    record = service.create(payload())
    service.analyze(record.id, "workspace-a", "analyst-1")

    status = service.status("workspace-a")
    assert status.snapshots == 1
    assert status.critical_modules == 1
    assert status.active_alerts >= 1
    assert service.get(record.id, "workspace-b") is None
    assert service.list_snapshots("workspace-b") == []


def test_duplicate_snapshot_is_rejected():
    service = ExecutiveOperationsService()
    service.create(payload())
    with pytest.raises(ValueError, match="already exists"):
        service.create(payload())


def test_module_names_must_be_unique():
    request = payload()
    request.signals.append(request.signals[0])
    with pytest.raises(ValueError, match="unique"):
        OperationsSnapshotCreate.model_validate(request.model_dump())
