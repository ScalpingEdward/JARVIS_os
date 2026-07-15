from uuid import UUID

from fastapi import APIRouter, HTTPException

from .models import (
    ToolInvocation,
    ToolListResponse,
    ToolRecord,
    ToolRegistration,
    ToolRunListResponse,
    ToolRunRecord,
)
from .service import ToolError, tool_gateway_service

router = APIRouter(prefix="/v1/tools", tags=["tools"])


def _call(operation):
    try:
        return operation()
    except ToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=ToolListResponse)
def list_tools() -> ToolListResponse:
    items = tool_gateway_service.list_tools()
    return ToolListResponse(items=items, count=len(items))


@router.post("", response_model=ToolRecord)
def register_tool(payload: ToolRegistration) -> ToolRecord:
    return tool_gateway_service.register(payload)


@router.post("/{tool_id}/enable", response_model=ToolRecord)
def enable_tool(tool_id: UUID) -> ToolRecord:
    return _call(lambda: tool_gateway_service.set_enabled(tool_id, True))


@router.post("/{tool_id}/disable", response_model=ToolRecord)
def disable_tool(tool_id: UUID) -> ToolRecord:
    return _call(lambda: tool_gateway_service.set_enabled(tool_id, False))


@router.post("/invoke", response_model=ToolRunRecord)
def invoke_tool(payload: ToolInvocation) -> ToolRunRecord:
    return _call(lambda: tool_gateway_service.invoke(payload))


@router.get("/runs", response_model=ToolRunListResponse)
def list_tool_runs() -> ToolRunListResponse:
    items = tool_gateway_service.list_runs()
    return ToolRunListResponse(items=items, count=len(items))
