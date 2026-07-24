from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_production_certification_release_gate import (
    AgentProductionCertificationAction,
    AgentProductionCertificationCreate,
    AgentProductionCertificationRecord,
)
from app.services.agent_production_certification_release_gate import (
    agent_production_certification_release_gate_service,
)


router = APIRouter(
    prefix="/v1/agent-production-certification",
    tags=["agent-production-certification"],
)


@router.get("/status")
def status() -> dict:
    return agent_production_certification_release_gate_service.status()


@router.post("/records", response_model=AgentProductionCertificationRecord)
def create_record(payload: AgentProductionCertificationCreate) -> AgentProductionCertificationRecord:
    try:
        return agent_production_certification_release_gate_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AgentProductionCertificationRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[AgentProductionCertificationRecord]:
    return agent_production_certification_release_gate_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AgentProductionCertificationRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> AgentProductionCertificationRecord:
    try:
        return agent_production_certification_release_gate_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AgentProductionCertificationRecord)
def act(record_id: str, payload: AgentProductionCertificationAction) -> AgentProductionCertificationRecord:
    try:
        return agent_production_certification_release_gate_service.act(
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
    return [
        entry.__dict__
        for entry in agent_production_certification_release_gate_service.audit(workspace_id)
    ]
