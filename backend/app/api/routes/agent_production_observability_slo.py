from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_production_observability_slo import (
    AgentProductionObservabilityAction,
    AgentProductionObservabilityCreate,
    AgentProductionObservabilityRecord,
)
from app.services.agent_production_observability_slo import (
    agent_production_observability_slo_service,
)


router = APIRouter(
    prefix="/v1/agent-production-observability",
    tags=["agent-production-observability"],
)


@router.get("/status")
def status() -> dict:
    return agent_production_observability_slo_service.status()


@router.post("/records", response_model=AgentProductionObservabilityRecord)
def create_record(payload: AgentProductionObservabilityCreate) -> AgentProductionObservabilityRecord:
    try:
        return agent_production_observability_slo_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AgentProductionObservabilityRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[AgentProductionObservabilityRecord]:
    return agent_production_observability_slo_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AgentProductionObservabilityRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> AgentProductionObservabilityRecord:
    try:
        return agent_production_observability_slo_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AgentProductionObservabilityRecord)
def act(record_id: str, payload: AgentProductionObservabilityAction) -> AgentProductionObservabilityRecord:
    try:
        return agent_production_observability_slo_service.act(
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
    return [entry.__dict__ for entry in agent_production_observability_slo_service.audit(workspace_id)]
