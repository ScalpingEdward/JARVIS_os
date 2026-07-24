from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_resilience_improvement_verification import (
    AgentResilienceImprovementAction,
    AgentResilienceImprovementCreate,
    AgentResilienceImprovementRecord,
)
from app.services.agent_resilience_improvement_verification import (
    agent_resilience_improvement_verification_service,
)

router = APIRouter(prefix="/v1/agent-resilience-improvements", tags=["agent-resilience-improvements"])


@router.get("/status")
def status() -> dict:
    return agent_resilience_improvement_verification_service.status()


@router.post("/records", response_model=AgentResilienceImprovementRecord)
def create_record(payload: AgentResilienceImprovementCreate) -> AgentResilienceImprovementRecord:
    try:
        return agent_resilience_improvement_verification_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AgentResilienceImprovementRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[AgentResilienceImprovementRecord]:
    return agent_resilience_improvement_verification_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AgentResilienceImprovementRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> AgentResilienceImprovementRecord:
    try:
        return agent_resilience_improvement_verification_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AgentResilienceImprovementRecord)
def act(record_id: str, payload: AgentResilienceImprovementAction) -> AgentResilienceImprovementRecord:
    try:
        return agent_resilience_improvement_verification_service.act(
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
    return [entry.__dict__ for entry in agent_resilience_improvement_verification_service.audit(workspace_id)]
