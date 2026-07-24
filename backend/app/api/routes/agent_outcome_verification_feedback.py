from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_outcome_verification_feedback import (
    AgentOutcomeVerificationAction,
    AgentOutcomeVerificationCreate,
    AgentOutcomeVerificationRecord,
)
from app.services.agent_outcome_verification_feedback import agent_outcome_verification_feedback_service


router = APIRouter(prefix="/v1/agent-outcome-verification", tags=["agent-outcome-verification"])


@router.get("/status")
def status() -> dict:
    return agent_outcome_verification_feedback_service.status()


@router.post("/records", response_model=AgentOutcomeVerificationRecord)
def create_record(payload: AgentOutcomeVerificationCreate) -> AgentOutcomeVerificationRecord:
    try:
        return agent_outcome_verification_feedback_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AgentOutcomeVerificationRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[AgentOutcomeVerificationRecord]:
    return agent_outcome_verification_feedback_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AgentOutcomeVerificationRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> AgentOutcomeVerificationRecord:
    try:
        return agent_outcome_verification_feedback_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AgentOutcomeVerificationRecord)
def act(record_id: str, payload: AgentOutcomeVerificationAction) -> AgentOutcomeVerificationRecord:
    try:
        return agent_outcome_verification_feedback_service.act(
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
    return [entry.__dict__ for entry in agent_outcome_verification_feedback_service.audit(workspace_id)]
