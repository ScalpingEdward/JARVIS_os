from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

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
)
from .service import plugin_sdk_service


class HeartbeatPayload(BaseModel):
    healthy: bool = True
    message: str = Field(default="", max_length=500)


router = APIRouter(prefix="/v1/plugin-sdk", tags=["plugin-sdk"])


@router.get("/status", response_model=PluginSDKStatus)
def sdk_status() -> PluginSDKStatus:
    return plugin_sdk_service.status()


@router.post("/plugins", response_model=PluginRecord, status_code=status.HTTP_201_CREATED)
def register_plugin(payload: PluginManifest) -> PluginRecord:
    try:
        return plugin_sdk_service.register(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/plugins", response_model=list[PluginRecord])
def list_plugins(workspace_id: str = Query(min_length=1, max_length=120)) -> list[PluginRecord]:
    return plugin_sdk_service.list_plugins(workspace_id)


@router.get("/plugins/{plugin_id}", response_model=PluginRecord)
def get_plugin(plugin_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> PluginRecord:
    plugin = plugin_sdk_service.get(plugin_id, workspace_id)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return plugin


@router.post("/plugins/{plugin_id}/activate", response_model=PluginRecord)
def activate_plugin(
    plugin_id: UUID,
    payload: PluginMutation,
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
) -> PluginRecord:
    plugin = plugin_sdk_service.activate(plugin_id, workspace_id, requester_id, payload)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Owned plugin not found")
    return plugin


@router.post("/plugins/{plugin_id}/disable", response_model=PluginRecord)
def disable_plugin(
    plugin_id: UUID,
    payload: PluginMutation,
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
) -> PluginRecord:
    plugin = plugin_sdk_service.disable(plugin_id, workspace_id, requester_id, payload)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Owned plugin not found")
    return plugin


@router.put("/plugins/{plugin_id}/permissions", response_model=PluginRecord)
def update_permission(
    plugin_id: UUID,
    payload: PermissionUpdate,
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
) -> PluginRecord:
    plugin = plugin_sdk_service.update_permission(plugin_id, workspace_id, requester_id, payload)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin or permission not found")
    return plugin


@router.post("/plugins/{plugin_id}/heartbeat", response_model=PluginRecord)
def plugin_heartbeat(
    plugin_id: UUID,
    payload: HeartbeatPayload,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> PluginRecord:
    plugin = plugin_sdk_service.heartbeat(plugin_id, workspace_id, payload.healthy, payload.message)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return plugin


@router.get("/capabilities/{capability}", response_model=list[PluginRecord])
def discover_capability(
    capability: str,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> list[PluginRecord]:
    return plugin_sdk_service.discover(workspace_id, capability)


@router.post("/plugins/{plugin_id}/invoke", response_model=InvocationRecord, status_code=status.HTTP_202_ACCEPTED)
def invoke_plugin(plugin_id: UUID, payload: PluginInvocation) -> InvocationRecord:
    record = plugin_sdk_service.invoke(plugin_id, payload)
    if record is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return record


@router.get("/invocations", response_model=list[InvocationRecord])
def list_invocations(workspace_id: str = Query(min_length=1, max_length=120)) -> list[InvocationRecord]:
    return plugin_sdk_service.list_invocations(workspace_id)


@router.post("/events", response_model=EventRecord, status_code=status.HTTP_201_CREATED)
def publish_event(payload: EventPublish) -> EventRecord:
    return plugin_sdk_service.publish_event(payload)


@router.get("/events", response_model=list[EventRecord])
def list_events(workspace_id: str = Query(min_length=1, max_length=120)) -> list[EventRecord]:
    return plugin_sdk_service.list_events(workspace_id)
