import pytest
from pydantic import ValidationError

from app.plugin_sdk.models import (
    EventPublish,
    PermissionGrant,
    PermissionRisk,
    PermissionUpdate,
    PluginInvocation,
    PluginManifest,
    PluginMutation,
    PluginState,
)
from app.plugin_sdk.service import PluginSDKService


def manifest(**overrides) -> PluginManifest:
    values = {
        "workspace_id": "phoenix-main",
        "owner_id": "owner-1",
        "plugin_key": "instagram.content",
        "name": "Instagram Content",
        "version": "1.0.0",
        "author": "PHOENIX",
        "capabilities": ["generate_caption", "prepare_post"],
        "permissions": [
            PermissionGrant(permission="media.read", risk=PermissionRisk.READ, granted=True),
            PermissionGrant(permission="instagram.publish", risk=PermissionRisk.EXTERNAL, granted=False),
        ],
        "subscriptions": ["content.approved"],
    }
    values.update(overrides)
    return PluginManifest(**values)


def test_plugin_register_activate_and_discover() -> None:
    service = PluginSDKService()
    plugin = service.register(manifest())
    assert plugin.state == PluginState.REGISTERED
    plugin = service.activate(plugin.id, "phoenix-main", "owner-1", PluginMutation())
    assert plugin.state == PluginState.ACTIVE
    assert service.discover("phoenix-main", "generate_caption") == [plugin]


def test_workspace_isolation_and_owner_control() -> None:
    service = PluginSDKService()
    plugin = service.register(manifest())
    assert service.get(plugin.id, "other") is None
    assert service.activate(plugin.id, "phoenix-main", "other-owner", PluginMutation()) is None


def test_incompatible_plugin_is_quarantined() -> None:
    service = PluginSDKService()
    plugin = service.register(manifest(plugin_key="future", api_version="9.0"))
    assert plugin.state == PluginState.QUARANTINED
    assert "Unsupported API" in plugin.health_message


def test_missing_dependency_prevents_activation() -> None:
    service = PluginSDKService()
    plugin = service.register(manifest(plugin_key="dependent", dependencies=["base.plugin"]))
    plugin = service.activate(plugin.id, "phoenix-main", "owner-1", PluginMutation())
    assert plugin.state == PluginState.QUARANTINED
    assert "Missing dependencies" in plugin.health_message


def test_permission_gateway_blocks_and_allows_sandbox_invocation() -> None:
    service = PluginSDKService()
    plugin = service.register(manifest())
    service.activate(plugin.id, "phoenix-main", "owner-1", PluginMutation())
    blocked = service.invoke(
        plugin.id,
        PluginInvocation(
            workspace_id="phoenix-main",
            requester_id="owner-1",
            capability="prepare_post",
            requested_permissions=["instagram.publish"],
        ),
    )
    assert blocked is not None and blocked.permitted is False
    service.update_permission(
        plugin.id,
        "phoenix-main",
        "owner-1",
        PermissionUpdate(permission="instagram.publish", granted=True),
    )
    allowed = service.invoke(
        plugin.id,
        PluginInvocation(
            workspace_id="phoenix-main",
            requester_id="owner-1",
            capability="prepare_post",
            requested_permissions=["instagram.publish"],
        ),
    )
    assert allowed is not None and allowed.permitted is True
    assert allowed.sandboxed is True
    assert allowed.result["status"] == "accepted_for_sandbox"


def test_event_bus_routes_only_to_active_subscribers_in_workspace() -> None:
    service = PluginSDKService()
    plugin = service.register(manifest())
    service.activate(plugin.id, "phoenix-main", "owner-1", PluginMutation())
    event = service.publish_event(
        EventPublish(
            workspace_id="phoenix-main",
            publisher_id="workflow-engine",
            event_type="content.approved",
            payload={"post_id": "123"},
        )
    )
    assert event.subscriber_plugin_ids == [plugin.id]
    assert service.list_events("other") == []


def test_health_and_disable_lifecycle() -> None:
    service = PluginSDKService()
    plugin = service.register(manifest())
    service.activate(plugin.id, "phoenix-main", "owner-1", PluginMutation())
    plugin = service.heartbeat(plugin.id, "phoenix-main", False, "Timeout")
    assert plugin is not None and plugin.state == PluginState.DEGRADED
    plugin = service.disable(plugin.id, "phoenix-main", "owner-1", PluginMutation(reason="Maintenance"))
    assert plugin is not None and plugin.state == PluginState.DISABLED


def test_duplicate_key_and_unsafe_external_actions_are_rejected() -> None:
    service = PluginSDKService()
    service.register(manifest())
    with pytest.raises(ValueError):
        service.register(manifest())
    with pytest.raises(ValidationError):
        manifest(plugin_key="unsafe", automatic_external_action=True)
    with pytest.raises(ValidationError):
        PluginInvocation(
            workspace_id="phoenix-main",
            requester_id="owner-1",
            capability="prepare_post",
            external_action=True,
        )
