import pytest

from app.command_center.models import (
    DashboardFilter,
    Priority,
    SignalCreate,
    SignalDomain,
    SignalState,
)
from app.command_center.service import CommandCenterService


def signal(
    key: str,
    state: SignalState,
    priority: Priority,
    domain: SignalDomain = SignalDomain.HEALTH,
    workspace: str = "ws",
    module: str = "health-intelligence",
) -> SignalCreate:
    return SignalCreate(
        workspace_id=workspace,
        reporter_id="dashboard-adapter",
        module=module,
        domain=domain,
        signal_key=key,
        title=key.replace("-", " ").title(),
        state=state,
        priority=priority,
        summary="Dashboard signal",
    )


def test_overview_aggregates_domains_and_priorities() -> None:
    service = CommandCenterService()
    service.record_signal(signal("api-health", SignalState.HEALTHY, Priority.MEDIUM))
    service.record_signal(signal("database-offline", SignalState.OFFLINE, Priority.CRITICAL, SignalDomain.SERVICE))
    service.record_signal(signal("compliance-warning", SignalState.WARNING, Priority.HIGH, SignalDomain.COMPLIANCE))

    overview = service.overview("ws")

    assert overview.total_signals == 3
    assert overview.overall_state == SignalState.OFFLINE
    assert overview.offline_signals == 1
    assert overview.warning_signals == 1
    assert overview.top_priorities[0].signal_key == "database-offline"
    assert 0 <= overview.readiness_score < 100
    assert {item.domain for item in overview.domains} == {
        SignalDomain.HEALTH,
        SignalDomain.SERVICE,
        SignalDomain.COMPLIANCE,
    }


def test_query_filters_and_workspace_isolation() -> None:
    service = CommandCenterService()
    service.record_signal(signal("health-a", SignalState.HEALTHY, Priority.LOW, workspace="a"))
    service.record_signal(signal("incident-a", SignalState.CRITICAL, Priority.CRITICAL, SignalDomain.INCIDENT, "a", "incident-management"))
    service.record_signal(signal("health-b", SignalState.WARNING, Priority.HIGH, workspace="b"))

    items = service.list_signals(DashboardFilter(
        workspace_id="a",
        domains=[SignalDomain.INCIDENT],
        states=[SignalState.CRITICAL],
    ))

    assert len(items) == 1
    assert items[0].signal_key == "incident-a"
    assert service.metrics("a").signal_records == 2
    assert service.metrics("b").signal_records == 1


def test_timeline_and_metrics_are_workspace_scoped() -> None:
    service = CommandCenterService()
    service.record_signal(signal("one", SignalState.HEALTHY, Priority.LOW))
    service.record_signal(signal("two", SignalState.DEGRADED, Priority.HIGH, SignalDomain.AGENT, module="agent-orchestrator"))

    timeline = service.timeline("ws")
    metrics = service.metrics("ws")

    assert len(timeline) == 2
    assert metrics.monitored_modules == 2
    assert metrics.monitored_domains == 2
    assert metrics.critical_items == 0
    assert len(service.list_audit("ws")) == 2


def test_empty_workspace_is_unknown_and_fully_ready() -> None:
    service = CommandCenterService()
    overview = service.overview("empty")
    assert overview.overall_state == SignalState.UNKNOWN
    assert overview.readiness_score == 100
    assert overview.total_signals == 0


def test_safety_controls_block_execution() -> None:
    with pytest.raises(ValueError):
        SignalCreate(
            workspace_id="ws",
            reporter_id="agent",
            module="command-center",
            domain=SignalDomain.WORKFLOW,
            signal_key="unsafe-action",
            title="Unsafe action",
            state=SignalState.CRITICAL,
            priority=Priority.CRITICAL,
            execute_action=True,
        )
