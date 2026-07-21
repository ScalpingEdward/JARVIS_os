from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from .models import (
    ObservabilityExecuteRequest,
    ProductionObservabilityAudit,
    ProductionObservabilityCreate,
    ProductionObservabilityRecord,
    ProductionObservabilityStatus,
)
from .service import production_observability_service

router = APIRouter(prefix="/v1/executive-production-observability", tags=["executive-production-observability"])


@router.get("/status", response_model=ProductionObservabilityStatus)
def status(workspace_id: str = Query(..., min_length=1)):
    return production_observability_service.status(workspace_id)


@router.post("/records", response_model=ProductionObservabilityRecord)
def create_record(payload: ProductionObservabilityCreate):
    try:
        return production_observability_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ProductionObservabilityRecord])
def list_records(workspace_id: str = Query(..., min_length=1)):
    return production_observability_service.list_records(workspace_id)


@router.get("/records/{record_id}", response_model=ProductionObservabilityRecord)
def get_record(record_id: UUID, workspace_id: str = Query(..., min_length=1)):
    record = production_observability_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="observability record not found")
    return record


@router.post("/records/{record_id}/execute", response_model=ProductionObservabilityRecord)
def execute_record(record_id: UUID, payload: ObservabilityExecuteRequest, workspace_id: str = Query(..., min_length=1)):
    try:
        return production_observability_service.execute(record_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[ProductionObservabilityAudit])
def audit(workspace_id: str = Query(..., min_length=1)):
    return production_observability_service.audit_records(workspace_id)
