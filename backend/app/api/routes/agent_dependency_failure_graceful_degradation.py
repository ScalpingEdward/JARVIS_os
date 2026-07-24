from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_dependency_failure_graceful_degradation import (
    DependencyFailureAction,
    DependencyFailureCreate,
    DependencyFailureRecord,
)
from app.services.agent_dependency_failure_graceful_degradation import (
    agent_dependency_failure_graceful_degradation_service,
)

router = APIRouter(prefix="/v1/agent-dependency-failure", tags=["agent-dependency-failure"])


@router.get("/status")
def status() -> dict:
    return agent_dependency_failure_graceful_degradation_service.status()


@router.post("/records", response_model=DependencyFailureRecord)
def create_record(payload: DependencyFailureCreate) -> DependencyFailureRecord:
    try:
        return agent_dependency_failure_graceful_degradation_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[DependencyFailureRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[DependencyFailureRecord]:
    return agent_dependency_failure_graceful_degradation_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=DependencyFailureRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> DependencyFailureRecord:
    try:
        return agent_dependency_failure_graceful_degradation_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=DependencyFailureRecord)
def act(record_id: str, payload: DependencyFailureAction) -> DependencyFailureRecord:
    try:
        return agent_dependency_failure_graceful_degradation_service.act(
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
    return [entry.__dict__ for entry in agent_dependency_failure_graceful_degradation_service.audit(workspace_id)]
