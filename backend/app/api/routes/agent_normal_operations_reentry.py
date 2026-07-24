from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_normal_operations_reentry import (
    NormalOperationsReentryAction,
    NormalOperationsReentryCreate,
    NormalOperationsReentryRecord,
)
from app.services.agent_normal_operations_reentry import agent_normal_operations_reentry_service

router = APIRouter(prefix="/v1/agent-normal-operations-reentry", tags=["agent-normal-operations-reentry"])


@router.get("/status")
def status() -> dict:
    return agent_normal_operations_reentry_service.status()


@router.post("/records", response_model=NormalOperationsReentryRecord)
def create_record(payload: NormalOperationsReentryCreate) -> NormalOperationsReentryRecord:
    try:
        return agent_normal_operations_reentry_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[NormalOperationsReentryRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[NormalOperationsReentryRecord]:
    return agent_normal_operations_reentry_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=NormalOperationsReentryRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> NormalOperationsReentryRecord:
    try:
        return agent_normal_operations_reentry_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=NormalOperationsReentryRecord)
def act(record_id: str, payload: NormalOperationsReentryAction) -> NormalOperationsReentryRecord:
    try:
        return agent_normal_operations_reentry_service.act(
            payload.workspace_id, record_id, payload.action, payload.actor, payload.operation_id, payload.reason
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return [entry.__dict__ for entry in agent_normal_operations_reentry_service.audit(workspace_id)]
