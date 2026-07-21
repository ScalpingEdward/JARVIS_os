from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from .models import (
    IncidentLearningAudit,
    IncidentLearningCreate,
    IncidentLearningExecuteRequest,
    IncidentLearningRecord,
    IncidentLearningStatus,
)
from .service import incident_learning_service


router = APIRouter(prefix="/v1/executive-incident-learning", tags=["executive-incident-learning"])


@router.get("/status", response_model=IncidentLearningStatus)
def status(workspace_id: str = Query(..., min_length=1)) -> IncidentLearningStatus:
    return incident_learning_service.status(workspace_id)


@router.post("/records", response_model=IncidentLearningRecord)
def create_record(payload: IncidentLearningCreate) -> IncidentLearningRecord:
    try:
        return incident_learning_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[IncidentLearningRecord])
def list_records(workspace_id: str = Query(..., min_length=1)) -> list[IncidentLearningRecord]:
    return incident_learning_service.list_records(workspace_id)


@router.get("/records/{record_id}", response_model=IncidentLearningRecord)
def get_record(record_id: UUID, workspace_id: str = Query(..., min_length=1)) -> IncidentLearningRecord:
    record = incident_learning_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="incident learning record not found")
    return record


@router.post("/records/{record_id}/execute", response_model=IncidentLearningRecord)
def execute_record(record_id: UUID, payload: IncidentLearningExecuteRequest, workspace_id: str = Query(..., min_length=1)) -> IncidentLearningRecord:
    try:
        return incident_learning_service.execute(record_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[IncidentLearningAudit])
def audit(workspace_id: str = Query(..., min_length=1)) -> list[IncidentLearningAudit]:
    return incident_learning_service.audit_records(workspace_id)
