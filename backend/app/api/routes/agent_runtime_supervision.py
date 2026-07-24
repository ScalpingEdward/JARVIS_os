from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_runtime_supervision import (
    AgentRuntimeAction,
    AgentRuntimeCreate,
    AgentRuntimeRecord,
)
from app.services.agent_runtime_supervision import agent_runtime_supervision_service


router = APIRouter(prefix="/v1/agent-runtime-supervision", tags=["agent-runtime-supervision"])


@router.get("/status")
def status() -> dict:
    return agent_runtime_supervision_service.status()


@router.post("/records", response_model=AgentRuntimeRecord)
def create_record(payload: AgentRuntimeCreate) -> AgentRuntimeRecord:
    try:
        return agent_runtime_supervision_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AgentRuntimeRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[AgentRuntimeRecord]:
    return agent_runtime_supervision_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AgentRuntimeRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> AgentRuntimeRecord:
    try:
        return agent_runtime_supervision_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AgentRuntimeRecord)
def act(record_id: str, payload: AgentRuntimeAction) -> AgentRuntimeRecord:
    try:
        return agent_runtime_supervision_service.act(
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
    return [entry.__dict__ for entry in agent_runtime_supervision_service.audit(workspace_id)]
