from datetime import datetime, timezone
from uuid import UUID

from .models import (
    EventPublish,
    EventRecord,
    InvocationRecord,
    PermissionUpdate,
    PluginInvocation,
    PluginManifest,
    PluginMutation,
    PluginRecord,
    PluginSDKStatus,
    PluginState,
)


CORE_VERSION = "7.9"
API_VERSION = "1.0"


class PluginSDKService:
    def __init__(self) -> None:
        self._plugins: dict[UUID, PluginRecord] = {}
        self._invocations: dict[UUID, InvocationRecord] = {}
        self._events: dict[UUID, EventRecord] = {}

    def status(self) -> PluginSDKStatus:
        plugins = list(self._plugins.values())
        capabilities = {cap for plugin in plugins for cap in plugin.capabilities}
        return PluginSDKStatus(
            registered_plugins=len(plugins),
            active_plugins=sum(item.state == PluginState.ACTIVE for item in plugins),
            degraded_plugins=sum(item.state == PluginState.DEGRADED for item in plugins),
            quarantined_plugins=sum(item.state == PluginState.QUARANTINED for item in plugins),
            total_capabilities=len(capabilities),
            published_events=len(self._events),
        )

    def register(self, payload: PluginManifest) -> PluginRecord:
        if any(
            item.workspace_id == payload.workspace_id.strip()
            and item.plugin_key == payload.plugin_key.strip().lower()
            for item in self._plugins.values()
        ):
            raise ValueError("plugin_key already exists in workspace")
        record = PluginRecord(
            workspace_id=payload.workspace_id.strip(),
            owner_id=payload.owner_id.strip(),
            plugin_key=payload.plugin_key.strip().lower(),
            name=payload.name.strip(),
            version=payload.version.strip(),
            author=payload.author.strip(),
            api_version=payload.api_version.strip(),
            minimum_core_version=payload.minimum_core_version.strip(),
            maximum_core_version=payload.maximum_core_version.strip() if payload.maximum_core_version else None,
            capabilities=self._normalize(payload.capabilities),
            permissions=payload.permissions,
            dependencies=self._normalize(payload.dependencies),
            subscriptions=self._normalize(payload.subscriptions),
            timeout_seconds=payload.timeout_seconds,
            memory_limit_mb=payload.memory_limit_mb,
        )
        compatible, reason = self._compatible(record)
        if not compatible:
            record.state = PluginState.QUARANTINED
            record.health_message = reason
        self._plugins[record.id] = record
        return record

    def list_plugins(self, workspace_id: str) -> list[PluginRecord]:
        return sorted(
            [item for item in self._plugins.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
        )

    def get(self, plugin_id: UUID, workspace_id: str) -> PluginRecord | None:
        plugin = self._plugins.get(plugin_id)
        return plugin if plugin and plugin.workspace_id == workspace_id else None

    def activate(self, plugin_id: UUID, workspace_id: str, requester_id: str, payload: PluginMutation) -> PluginRecord | None:
        plugin = self._owned(plugin_id, workspace_id, requester_id)
        if plugin is None:
            return None
        compatible, reason = self._compatible(plugin)
        dependencies = {
            item.plugin_key
            for item in self._plugins.values()
            if item.workspace_id == workspace_id and item.state == PluginState.ACTIVE
        }
        missing = [item for item in plugin.dependencies if item not in dependencies]
        if not compatible or missing:
            plugin.state = PluginState.QUARANTINED
            plugin.health_message = reason if not compatible else f"Missing dependencies: {', '.join(missing)}"
        else:
            plugin.state = PluginState.ACTIVE
            plugin.health_message = "Healthy"
        plugin.updated_at = datetime.now(timezone.utc)
        return plugin

    def disable(self, plugin_id: UUID, workspace_id: str, requester_id: str, payload: PluginMutation) -> PluginRecord | None:
        plugin = self._owned(plugin_id, workspace_id, requester_id)
        if plugin is None:
            return None
        plugin.state = PluginState.DISABLED
        plugin.health_message = payload.reason.strip() or "Disabled by owner"
        plugin.updated_at = datetime.now(timezone.utc)
        return plugin

    def update_permission(
        self, plugin_id: UUID, workspace_id: str, requester_id: str, payload: PermissionUpdate
    ) -> PluginRecord | None:
        plugin = self._owned(plugin_id, workspace_id, requester_id)
        if plugin is None:
            return None
        permission = next((item for item in plugin.permissions if item.permission == payload.permission), None)
        if permission is None:
            return None
        permission.granted = payload.granted
        plugin.updated_at = datetime.now(timezone.utc)
        return plugin

    def heartbeat(self, plugin_id: UUID, workspace_id: str, healthy: bool, message: str) -> PluginRecord | None:
        plugin = self.get(plugin_id, workspace_id)
        if plugin is None:
            return None
        plugin.last_heartbeat_at = datetime.now(timezone.utc)
        plugin.health_message = message.strip() or ("Healthy" if healthy else "Health check failed")
        if plugin.state not in {PluginState.DISABLED, PluginState.QUARANTINED}:
            plugin.state = PluginState.ACTIVE if healthy else PluginState.DEGRADED
        plugin.updated_at = datetime.now(timezone.utc)
        return plugin

    def discover(self, workspace_id: str, capability: str) -> list[PluginRecord]:
        capability = capability.strip().lower()
        return [
            item
            for item in self.list_plugins(workspace_id)
            if item.state == PluginState.ACTIVE and capability in item.capabilities
        ]

    def invoke(self, plugin_id: UUID, payload: PluginInvocation) -> InvocationRecord | None:
        plugin = self.get(plugin_id, payload.workspace_id)
        if plugin is None:
            return None
        requested = self._normalize(payload.requested_permissions)
        granted = {item.permission for item in plugin.permissions if item.granted}
        capability_ok = payload.capability.strip().lower() in plugin.capabilities
        permissions_ok = all(item in granted for item in requested)
        permitted = plugin.state == PluginState.ACTIVE and capability_ok and permissions_ok
        error = None
        if plugin.state != PluginState.ACTIVE:
            error = "Plugin is not active"
        elif not capability_ok:
            error = "Capability is not provided by plugin"
        elif not permissions_ok:
            error = "One or more permissions are not granted"
        record = InvocationRecord(
            workspace_id=payload.workspace_id,
            plugin_id=plugin.id,
            capability=payload.capability.strip().lower(),
            input=payload.input,
            requested_permissions=requested,
            permitted=permitted,
            result={"status": "accepted_for_sandbox"} if permitted else {},
            error=error,
        )
        self._invocations[record.id] = record
        plugin.invocation_count += 1
        if not permitted:
            plugin.failure_count += 1
        return record

    def list_invocations(self, workspace_id: str) -> list[InvocationRecord]:
        return sorted(
            [item for item in self._invocations.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def publish_event(self, payload: EventPublish) -> EventRecord:
        subscribers = [
            item.id
            for item in self._plugins.values()
            if item.workspace_id == payload.workspace_id
            and item.state == PluginState.ACTIVE
            and payload.event_type in item.subscriptions
        ]
        record = EventRecord(
            workspace_id=payload.workspace_id.strip(),
            publisher_id=payload.publisher_id.strip(),
            event_type=payload.event_type.strip().lower(),
            payload=payload.payload,
            subscriber_plugin_ids=subscribers,
        )
        self._events[record.id] = record
        return record

    def list_events(self, workspace_id: str) -> list[EventRecord]:
        return sorted(
            [item for item in self._events.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def _owned(self, plugin_id: UUID, workspace_id: str, requester_id: str) -> PluginRecord | None:
        plugin = self.get(plugin_id, workspace_id)
        return plugin if plugin and plugin.owner_id == requester_id else None

    @staticmethod
    def _normalize(values: list[str]) -> list[str]:
        return sorted({item.strip().lower() for item in values if item.strip()})

    @staticmethod
    def _version_tuple(value: str) -> tuple[int, ...]:
        try:
            return tuple(int(part) for part in value.split("."))
        except ValueError:
            return (0,)

    def _compatible(self, plugin: PluginRecord) -> tuple[bool, str]:
        if plugin.api_version != API_VERSION:
            return False, f"Unsupported API version {plugin.api_version}"
        core = self._version_tuple(CORE_VERSION)
        if core < self._version_tuple(plugin.minimum_core_version):
            return False, "Core version is below plugin minimum"
        if plugin.maximum_core_version and core > self._version_tuple(plugin.maximum_core_version):
            return False, "Core version is above plugin maximum"
        return True, "Compatible"


plugin_sdk_service = PluginSDKService()
