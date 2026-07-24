from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_post_incident_recovery_resilience import (
    AgentPostIncidentRecoveryAction,
    AgentPostIncidentRecoveryCreate,
    AgentPostIncidentRecoveryRecord,
)
from app.services.agent_post_incident_recovery_resilience import agent_post_incident_recovery_resilience_service

router = APIRouter(prefix="/v1/agent-post-incident-recovery", tags=["agent-post-incident-recovery"])


@router.get("/status")
def status() -> dict:
    return agent_post_incident_recovery_resilience_service.status()


@router.post("/records", response_model=AgentPostIncidentRecoveryRecord)
def create_record(payload: AgentPostIncidentRecoveryCreate) -> AgentPostIncidentRecoveryRecord:
    try:
        return agent_post_incident_recovery_resilience_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AgentPostIncidentRecoveryRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[AgentPostIncidentRecoveryRecord]:
    return agent_post_incident_recovery_resilience_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AgentPostIncidentRecoveryRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> AgentPostIncidentRecoveryRecord:
    try:
        return agent_post_incident_recovery_resilience_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AgentPostIncidentRecoveryRecord)
def act(record_id: str, payload: AgentPostIncidentRecoveryAction) -> AgentPostIncidentRecoveryRecord:
    try:
        return agent_post_incident_recovery_resilience_service.act(
            workspace_id=payload.workspace_id, record_id=record_id, action=payload.action,
            actor=payload.actor, operation_id=payload.operation_id, reason=payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return [entry.__dict__ for entry in agent_post_incident_recovery_resilience_service.audit(workspace_id)]
