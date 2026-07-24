from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_production_incident_response import (
    AgentProductionIncidentAction,
    AgentProductionIncidentCreate,
    AgentProductionIncidentRecord,
)
from app.services.agent_production_incident_response import agent_production_incident_response_service

router = APIRouter(prefix="/v1/agent-production-incidents", tags=["agent-production-incidents"])


@router.get("/status")
def status() -> dict:
    return agent_production_incident_response_service.status()


@router.post("/records", response_model=AgentProductionIncidentRecord)
def create_record(payload: AgentProductionIncidentCreate) -> AgentProductionIncidentRecord:
    try:
        return agent_production_incident_response_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AgentProductionIncidentRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[AgentProductionIncidentRecord]:
    return agent_production_incident_response_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AgentProductionIncidentRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> AgentProductionIncidentRecord:
    try:
        return agent_production_incident_response_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AgentProductionIncidentRecord)
def act(record_id: str, payload: AgentProductionIncidentAction) -> AgentProductionIncidentRecord:
    try:
        return agent_production_incident_response_service.act(
            workspace_id=payload.workspace_id, record_id=record_id, action=payload.action,
            actor=payload.actor, operation_id=payload.operation_id, reason=payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return [entry.__dict__ for entry in agent_production_incident_response_service.audit(workspace_id)]
