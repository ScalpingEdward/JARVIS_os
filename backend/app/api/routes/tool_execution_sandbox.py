from fastapi import APIRouter, HTTPException, Query

from app.schemas.tool_execution_sandbox import (
    ToolExecutionAction,
    ToolExecutionRecord,
    ToolExecutionRequest,
    ToolExecutionResult,
)
from app.services.tool_execution_sandbox import tool_execution_sandbox_service

router = APIRouter(prefix="/v1/tool-execution-sandbox", tags=["tool-execution-sandbox"])


@router.get("/status")
def status() -> dict:
    return tool_execution_sandbox_service.status()


@router.post("/records", response_model=ToolExecutionRecord)
def create_record(payload: ToolExecutionRequest) -> ToolExecutionRecord:
    try:
        return tool_execution_sandbox_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ToolExecutionRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[ToolExecutionRecord]:
    return tool_execution_sandbox_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=ToolExecutionRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> ToolExecutionRecord:
    try:
        return tool_execution_sandbox_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ToolExecutionRecord)
def act(record_id: str, payload: ToolExecutionAction) -> ToolExecutionRecord:
    try:
        return tool_execution_sandbox_service.act(
            payload.workspace_id, record_id, payload.action, payload.actor, payload.operation_id, payload.reason
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/records/{record_id}/result", response_model=ToolExecutionRecord)
def record_result(record_id: str, payload: ToolExecutionResult) -> ToolExecutionRecord:
    try:
        return tool_execution_sandbox_service.record_result(record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return tool_execution_sandbox_service.audit(workspace_id)
