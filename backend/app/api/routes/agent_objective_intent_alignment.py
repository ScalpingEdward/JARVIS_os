from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_objective_intent_alignment import (
    AgentObjectiveAction,
    AgentObjectiveCreate,
    AgentObjectiveRecord,
)
from app.services.agent_objective_intent_alignment import agent_objective_intent_alignment_service

router = APIRouter(prefix="/v1/agent-objective-alignment", tags=["agent-objective-alignment"])


@router.get("/status")
def status() -> dict:
    return agent_objective_intent_alignment_service.status()


@router.post("/records", response_model=AgentObjectiveRecord)
def create_record(payload: AgentObjectiveCreate) -> AgentObjectiveRecord:
    try:
        return agent_objective_intent_alignment_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AgentObjectiveRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[AgentObjectiveRecord]:
    return agent_objective_intent_alignment_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AgentObjectiveRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> AgentObjectiveRecord:
    try:
        return agent_objective_intent_alignment_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AgentObjectiveRecord)
def act(record_id: str, payload: AgentObjectiveAction) -> AgentObjectiveRecord:
    try:
        return agent_objective_intent_alignment_service.act(
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
    return [entry.__dict__ for entry in agent_objective_intent_alignment_service.audit(workspace_id)]
