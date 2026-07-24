from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_authorization_tool_use import (
    AgentAuthorizationAction,
    AgentAuthorizationCreate,
    AgentAuthorizationRecord,
)
from app.services.agent_authorization_tool_use import agent_authorization_tool_use_service


router = APIRouter(prefix="/v1/agent-authorization", tags=["agent-authorization"])


@router.get("/status")
def status() -> dict:
    return agent_authorization_tool_use_service.status()


@router.post("/records", response_model=AgentAuthorizationRecord)
def create_record(payload: AgentAuthorizationCreate) -> AgentAuthorizationRecord:
    try:
        return agent_authorization_tool_use_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AgentAuthorizationRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[AgentAuthorizationRecord]:
    return agent_authorization_tool_use_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AgentAuthorizationRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> AgentAuthorizationRecord:
    try:
        return agent_authorization_tool_use_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AgentAuthorizationRecord)
def act(record_id: str, payload: AgentAuthorizationAction) -> AgentAuthorizationRecord:
    try:
        return agent_authorization_tool_use_service.act(
            workspace_id=payload.workspace_id,
            record_id=record_id,
            action=payload.action,
            actor=payload.actor,
            operation_id=payload.operation_id,
            reason=payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return [entry.__dict__ for entry in agent_authorization_tool_use_service.audit(workspace_id)]
