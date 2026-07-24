from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_crisis_simulation_recovery_exercise import (
    CrisisExerciseAction,
    CrisisExerciseCreate,
    CrisisExerciseRecord,
)
from app.services.agent_crisis_simulation_recovery_exercise import (
    agent_crisis_simulation_recovery_exercise_service,
)

router = APIRouter(prefix="/v1/agent-crisis-exercises", tags=["agent-crisis-exercises"])


@router.get("/status")
def status() -> dict:
    return agent_crisis_simulation_recovery_exercise_service.status()


@router.post("/records", response_model=CrisisExerciseRecord)
def create_record(payload: CrisisExerciseCreate) -> CrisisExerciseRecord:
    try:
        return agent_crisis_simulation_recovery_exercise_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[CrisisExerciseRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[CrisisExerciseRecord]:
    return agent_crisis_simulation_recovery_exercise_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=CrisisExerciseRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> CrisisExerciseRecord:
    try:
        return agent_crisis_simulation_recovery_exercise_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=CrisisExerciseRecord)
def act(record_id: str, payload: CrisisExerciseAction) -> CrisisExerciseRecord:
    try:
        return agent_crisis_simulation_recovery_exercise_service.act(
            payload.workspace_id,
            record_id,
            payload.action,
            payload.actor,
            payload.operation_id,
            payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return [entry.__dict__ for entry in agent_crisis_simulation_recovery_exercise_service.audit(workspace_id)]
