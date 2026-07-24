from fastapi import APIRouter, HTTPException, Query

from app.schemas.operational_resilience_incident import (
    OperationalResilienceAction,
    OperationalResilienceCreate,
    OperationalResilienceRecord,
)
from app.services.operational_resilience_incident import operational_resilience_incident_service

router = APIRouter(prefix="/v1/operational-resilience", tags=["operational-resilience"])


@router.get("/status")
def get_status() -> dict:
    return operational_resilience_incident_service.status()


@router.post("/records", response_model=OperationalResilienceRecord)
def create_record(payload: OperationalResilienceCreate) -> OperationalResilienceRecord:
    try:
        return operational_resilience_incident_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[OperationalResilienceRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[OperationalResilienceRecord]:
    return operational_resilience_incident_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=OperationalResilienceRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> OperationalResilienceRecord:
    try:
        return operational_resilience_incident_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=OperationalResilienceRecord)
def act_on_record(record_id: str, payload: OperationalResilienceAction) -> OperationalResilienceRecord:
    try:
        return operational_resilience_incident_service.act(
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
def get_audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return [entry.__dict__ for entry in operational_resilience_incident_service.audit(workspace_id)]
