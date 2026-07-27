from fastapi import APIRouter, HTTPException, Query

from app.schemas.controlled_tool_invocation_gateway import (
    ToolInvocationAction,
    ToolInvocationCreate,
    ToolInvocationRecord,
    ToolInvocationResult,
)
from app.services.controlled_tool_invocation_gateway import controlled_tool_invocation_gateway_service as service

router = APIRouter(prefix="/v1/tool-invocation-gateway", tags=["tool-invocation-gateway"])


@router.get("/status")
def status() -> dict:
    return service.status()


@router.post("/records", response_model=ToolInvocationRecord)
def create_record(payload: ToolInvocationCreate) -> ToolInvocationRecord:
    try:
        return service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ToolInvocationRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[ToolInvocationRecord]:
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=ToolInvocationRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> ToolInvocationRecord:
    try:
        return service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ToolInvocationRecord)
def act(record_id: str, payload: ToolInvocationAction) -> ToolInvocationRecord:
    try:
        return service.act(payload.workspace_id, record_id, payload.action, payload.actor, payload.operation_id, payload.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/records/{record_id}/result", response_model=ToolInvocationRecord)
def ingest_result(record_id: str, payload: ToolInvocationResult) -> ToolInvocationRecord:
    try:
        return service.ingest_result(record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return service.audit(workspace_id)
