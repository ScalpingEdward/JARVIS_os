from fastapi import APIRouter, HTTPException, Query

from app.schemas.execution_outcome_trust_feedback import OutcomeTrustAction, OutcomeTrustCreate, OutcomeTrustRecord
from app.services.execution_outcome_trust_feedback import execution_outcome_trust_feedback_service as service

router = APIRouter(prefix="/v1/execution-outcome-trust-feedback", tags=["execution-outcome-trust-feedback"])


@router.get("/status")
def status():
    return service.status()


@router.post("/records", response_model=OutcomeTrustRecord)
def create_record(payload: OutcomeTrustCreate):
    try:
        return service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[OutcomeTrustRecord])
def list_records(workspace_id: str = Query(min_length=1)):
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=OutcomeTrustRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)):
    try:
        return service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=OutcomeTrustRecord)
def act(record_id: str, payload: OutcomeTrustAction):
    try:
        return service.act(record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)):
    return service.audit(workspace_id)
