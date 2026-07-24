from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_memory_context_provenance import (
    AgentMemoryContextAction,
    AgentMemoryContextCreate,
    AgentMemoryContextRecord,
)
from app.services.agent_memory_context_provenance import agent_memory_context_provenance_service

router = APIRouter(prefix="/v1/agent-memory-context", tags=["agent-memory-context"])


@router.get("/status")
def status() -> dict:
    return agent_memory_context_provenance_service.status()


@router.post("/records", response_model=AgentMemoryContextRecord)
def create_record(payload: AgentMemoryContextCreate) -> AgentMemoryContextRecord:
    try:
        return agent_memory_context_provenance_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AgentMemoryContextRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[AgentMemoryContextRecord]:
    return agent_memory_context_provenance_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AgentMemoryContextRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> AgentMemoryContextRecord:
    try:
        return agent_memory_context_provenance_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AgentMemoryContextRecord)
def act(record_id: str, payload: AgentMemoryContextAction) -> AgentMemoryContextRecord:
    try:
        return agent_memory_context_provenance_service.act(
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
    return [entry.__dict__ for entry in agent_memory_context_provenance_service.audit(workspace_id)]
