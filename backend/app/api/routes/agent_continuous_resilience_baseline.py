from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_continuous_resilience_baseline import (
    AgentContinuousResilienceAction,
    AgentContinuousResilienceCreate,
    AgentContinuousResilienceRecord,
)
from app.services.agent_continuous_resilience_baseline import agent_continuous_resilience_baseline_service

router = APIRouter(prefix="/v1/agent-continuous-resilience", tags=["agent-continuous-resilience"])


@router.get("/status")
def status() -> dict:
    return agent_continuous_resilience_baseline_service.status()


@router.post("/records", response_model=AgentContinuousResilienceRecord)
def create_record(payload: AgentContinuousResilienceCreate) -> AgentContinuousResilienceRecord:
    try:
        return agent_continuous_resilience_baseline_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AgentContinuousResilienceRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[AgentContinuousResilienceRecord]:
    return agent_continuous_resilience_baseline_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AgentContinuousResilienceRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> AgentContinuousResilienceRecord:
    try:
        return agent_continuous_resilience_baseline_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AgentContinuousResilienceRecord)
def act(record_id: str, payload: AgentContinuousResilienceAction) -> AgentContinuousResilienceRecord:
    try:
        return agent_continuous_resilience_baseline_service.act(
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
    return [entry.__dict__ for entry in agent_continuous_resilience_baseline_service.audit(workspace_id)]
