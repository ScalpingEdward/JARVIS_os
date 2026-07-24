from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_learning_adaptation import AgentLearningAction, AgentLearningCreate, AgentLearningRecord
from app.services.agent_learning_adaptation import agent_learning_adaptation_service


router = APIRouter(prefix="/v1/agent-learning-adaptation", tags=["agent-learning-adaptation"])


@router.get("/status")
def status() -> dict:
    return agent_learning_adaptation_service.status()


@router.post("/records", response_model=AgentLearningRecord)
def create_record(payload: AgentLearningCreate) -> AgentLearningRecord:
    try:
        return agent_learning_adaptation_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AgentLearningRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[AgentLearningRecord]:
    return agent_learning_adaptation_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AgentLearningRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> AgentLearningRecord:
    try:
        return agent_learning_adaptation_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AgentLearningRecord)
def act(record_id: str, payload: AgentLearningAction) -> AgentLearningRecord:
    try:
        return agent_learning_adaptation_service.act(
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
    return [entry.__dict__ for entry in agent_learning_adaptation_service.audit(workspace_id)]
