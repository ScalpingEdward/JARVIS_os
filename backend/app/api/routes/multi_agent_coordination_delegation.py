from fastapi import APIRouter, HTTPException, Query

from app.schemas.multi_agent_coordination_delegation import (
    MultiAgentCoordinationAction,
    MultiAgentCoordinationCreate,
    MultiAgentCoordinationRecord,
)
from app.services.multi_agent_coordination_delegation import multi_agent_coordination_delegation_service


router = APIRouter(prefix="/v1/multi-agent-coordination", tags=["multi-agent-coordination"])


@router.get("/status")
def status() -> dict:
    return multi_agent_coordination_delegation_service.status()


@router.post("/records", response_model=MultiAgentCoordinationRecord)
def create_record(payload: MultiAgentCoordinationCreate) -> MultiAgentCoordinationRecord:
    try:
        return multi_agent_coordination_delegation_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[MultiAgentCoordinationRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[MultiAgentCoordinationRecord]:
    return multi_agent_coordination_delegation_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=MultiAgentCoordinationRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> MultiAgentCoordinationRecord:
    try:
        return multi_agent_coordination_delegation_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=MultiAgentCoordinationRecord)
def act(record_id: str, payload: MultiAgentCoordinationAction) -> MultiAgentCoordinationRecord:
    try:
        return multi_agent_coordination_delegation_service.act(
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
    return [entry.__dict__ for entry in multi_agent_coordination_delegation_service.audit(workspace_id)]
