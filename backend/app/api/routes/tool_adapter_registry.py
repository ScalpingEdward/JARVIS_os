from fastapi import APIRouter, HTTPException, Query

from app.schemas.tool_adapter_registry import (
    ToolAdapterMatch,
    ToolAdapterMatchRequest,
    ToolAdapterRegistryAction,
    ToolAdapterRegistryCreate,
    ToolAdapterRegistryRecord,
)
from app.services.tool_adapter_registry import tool_adapter_registry_service

router = APIRouter(prefix="/v1/tool-adapters", tags=["tool-adapters"])


@router.get("/status")
def status() -> dict:
    return tool_adapter_registry_service.status()


@router.post("/records", response_model=ToolAdapterRegistryRecord)
def create_record(payload: ToolAdapterRegistryCreate) -> ToolAdapterRegistryRecord:
    try:
        return tool_adapter_registry_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ToolAdapterRegistryRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[ToolAdapterRegistryRecord]:
    return tool_adapter_registry_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=ToolAdapterRegistryRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> ToolAdapterRegistryRecord:
    try:
        return tool_adapter_registry_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ToolAdapterRegistryRecord)
def act(record_id: str, payload: ToolAdapterRegistryAction) -> ToolAdapterRegistryRecord:
    try:
        return tool_adapter_registry_service.act(
            payload.workspace_id, record_id, payload.action, payload.actor,
            payload.operation_id, payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/match", response_model=list[ToolAdapterMatch])
def match(payload: ToolAdapterMatchRequest) -> list[ToolAdapterMatch]:
    return tool_adapter_registry_service.match(payload)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return tool_adapter_registry_service.audit(workspace_id)
