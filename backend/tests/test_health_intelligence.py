import pytest

from app.health_intelligence.models import (
    AlertState, HealthRuleCreate, HealthState, MetricKind, Mutation,
    TargetKind, TelemetryCreate,
)
from app.health_intelligence.service import HealthIntelligenceService


def rule(workspace: str = "ws") -> HealthRuleCreate:
    return HealthRuleCreate(
        workspace_id=workspace,
        owner_id="owner",
        rule_key="api-latency",
        name="API latency",
        target_kind=TargetKind.SERVICE,
        metric_kind=MetricKind.API_LATENCY_MS,
        warning_threshold=200,
        critical_threshold=500,
    )


def telemetry(value: float, workspace: str = "ws") -> TelemetryCreate:
    return TelemetryCreate(
        workspace_id=workspace,
        reporter_id="collector",
        target_kind=TargetKind.SERVICE,
        target_key="telegram-parser",
        metric_kind=MetricKind.API_LATENCY_MS,
        value=value,
        unit="ms",
    )


def test_threshold_evaluation_opens_alert_and_snapshot() -> None:
    service = HealthIntelligenceService()
    service.create_rule(rule())
    service.record_telemetry(650)
    alerts = service.list_alerts("ws")
    assert len(alerts) == 1
    assert alerts[0].severity.value == "critical"
    snapshots = service.snapshots("ws")
    assert snapshots[0].state == HealthState.CRITICAL
    assert service.metrics("ws").critical_alerts == 1


def test_alert_lifecycle() -> None:
    service = HealthIntelligenceService()
    service.create_rule(rule())
    service.record_telemetry(250)
    alert = service.list_alerts("ws")[0]
    mutation = Mutation(requester_id="operator")
    assert service.mutate_alert(alert.id, "ws", mutation, AlertState.ACKNOWLEDGED).state == AlertState.ACKNOWLEDGED
    assert service.mutate_alert(alert.id, "ws", mutation, AlertState.RESOLVED).state == AlertState.RESOLVED
    assert service.mutate_alert(alert.id, "ws", mutation, AlertState.ARCHIVED).state == AlertState.ARCHIVED


def test_workspace_isolation_and_duplicate_rule_keys() -> None:
    service = HealthIntelligenceService()
    service.create_rule(rule("a"))
    service.create_rule(rule("b"))
    assert len(service.list_rules("a")) == 1
    assert len(service.list_rules("b")) == 1
    with pytest.raises(ValueError):
        service.create_rule(rule("a"))


def test_duplicate_active_alert_is_suppressed() -> None:
    service = HealthIntelligenceService()
    service.create_rule(rule())
    service.record_telemetry(700)
    service.record_telemetry(800)
    assert len(service.list_alerts("ws")) == 1


def test_safety_controls() -> None:
    with pytest.raises(ValueError):
        TelemetryCreate(
            workspace_id="ws",
            reporter_id="collector",
            target_kind=TargetKind.SYSTEM,
            target_key="vps",
            metric_kind=MetricKind.CPU_PERCENT,
            value=90,
            execute_action=True,
        )
    with pytest.raises(ValueError):
        HealthRuleCreate(
            workspace_id="ws",
            owner_id="owner",
            rule_key="unsafe",
            name="Unsafe",
            target_kind=TargetKind.SYSTEM,
            metric_kind=MetricKind.CPU_PERCENT,
            warning_threshold=80,
            critical_threshold=90,
            automatic_remediation=True,
        )
