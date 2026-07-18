import pytest

from app.dashboard_governance.models import (
    DashboardViewCreate,
    DashboardViewUpdate,
    GridPlacement,
    RefreshMode,
    ViewMutation,
    ViewState,
    WidgetDefinition,
    WidgetKind,
)
from app.dashboard_governance.service import DashboardGovernanceService


def widget(key: str = "readiness") -> WidgetDefinition:
    return WidgetDefinition(
        widget_key=key,
        title="Readiness",
        kind=WidgetKind.KPI,
        data_source="/v1/command-center/overview",
        refresh_mode=RefreshMode.INTERVAL,
        refresh_seconds=60,
        allowed_roles=["operator", "admin"],
    )


def view(workspace: str = "ws", key: str = "executive") -> DashboardViewCreate:
    return DashboardViewCreate(
        workspace_id=workspace,
        owner_id="owner",
        view_key=key,
        name="Executive Overview",
        audience_roles=["operator", "admin"],
        widgets=[widget()],
        layout=[GridPlacement(widget_key="readiness", x=0, y=0, width=6, height=4)],
        is_default=True,
    )


def test_view_lifecycle_requires_independent_publisher() -> None:
    service = DashboardGovernanceService()
    item = service.create_view(view())
    assert item.state == ViewState.DRAFT

    reviewed = service.mutate_view(item.id, "ws", ViewMutation(requester_id="owner"), ViewState.REVIEW)
    assert reviewed.state == ViewState.REVIEW

    with pytest.raises(ValueError):
        service.mutate_view(item.id, "ws", ViewMutation(requester_id="owner"), ViewState.PUBLISHED)

    published = service.mutate_view(item.id, "ws", ViewMutation(requester_id="reviewer"), ViewState.PUBLISHED)
    assert published.state == ViewState.PUBLISHED
    assert published.published_by == "reviewer"


def test_update_versions_view_and_returns_to_draft() -> None:
    service = DashboardGovernanceService()
    item = service.create_view(view())
    service.mutate_view(item.id, "ws", ViewMutation(requester_id="owner"), ViewState.REVIEW)

    updated = service.update_view(
        item.id,
        "ws",
        DashboardViewUpdate(requester_id="owner", name="Operations Overview"),
    )
    assert updated.name == "Operations Overview"
    assert updated.version == 2
    assert updated.state == ViewState.DRAFT


def test_default_view_and_role_resolution() -> None:
    service = DashboardGovernanceService()
    first = service.create_view(view(key="executive"))
    second_payload = view(key="admin")
    second_payload.audience_roles = ["admin"]
    second_payload.is_default = False
    second = service.create_view(second_payload)

    for item in (first, second):
        service.mutate_view(item.id, "ws", ViewMutation(requester_id="owner"), ViewState.REVIEW)
        service.mutate_view(item.id, "ws", ViewMutation(requester_id="reviewer"), ViewState.PUBLISHED)

    assert service.resolve_view("ws", "operator").id == first.id
    assert service.resolve_view("ws", "admin").id == first.id
    assert service.resolve_view("ws", "viewer") is None


def test_workspace_isolation_and_duplicate_keys() -> None:
    service = DashboardGovernanceService()
    service.create_view(view("a"))
    service.create_view(view("b"))
    assert len(service.list_views("a")) == 1
    assert len(service.list_views("b")) == 1
    with pytest.raises(ValueError):
        service.create_view(view("a"))


def test_layout_and_safety_validation() -> None:
    with pytest.raises(ValueError):
        GridPlacement(widget_key="wide", x=20, y=0, width=8, height=4)

    with pytest.raises(ValueError):
        WidgetDefinition(
            widget_key="unsafe",
            title="Unsafe",
            kind=WidgetKind.STATUS,
            data_source="/unsafe",
            execute_action=True,
        )

    with pytest.raises(ValueError):
        DashboardViewCreate(
            workspace_id="ws",
            owner_id="owner",
            view_key="broken",
            name="Broken",
            widgets=[widget()],
            layout=[],
        )


def test_metrics_and_audit() -> None:
    service = DashboardGovernanceService()
    item = service.create_view(view())
    service.mutate_view(item.id, "ws", ViewMutation(requester_id="owner"), ViewState.REVIEW)
    metrics = service.metrics("ws")
    assert metrics.total_views == 1
    assert metrics.review_views == 1
    assert metrics.total_widgets == 1
    assert len(service.list_audit("ws")) == 2
