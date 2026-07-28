from fastapi import APIRouter, HTTPException, Query

from app.schemas.recovery_primary_permit import RecoveryPermitAction, RecoveryPermitConsume, RecoveryPermitCreate, RecoveryPermitRecord
from app.services.recovery_primary_permit import recovery_primary_permit_service as service

router = APIRouter(prefix="/v1/recovery-primary-permits", tags=["recovery-primary-permits"])


@router.get("/status")
def status():
    return service.status()


@router.post("/records", response_model=RecoveryPermitRecord)
def create_record(payload: RecoveryPermitCreate):
    try:
        return service.create(payload)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/records", response_model=list[RecoveryPermitRecord])
def list_records(workspace_id: str = Query(min_length=1)):
    return service.list(workspace_id)


@router.get("/records/{permit_id}", response_model=RecoveryPermitRecord)
def get_record(permit_id: str, workspace_id: str = Query(min_length=1)):
    try:
        return service.get(workspace_id, permit_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/records/{permit_id}/actions")
def act(permit_id: str, payload: RecoveryPermitAction):
    try:
        return service.act(payload.workspace_id, permit_id, payload.action, payload.actor, payload.operation_id, payload.reason)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/records/{permit_id}/consume", response_model=RecoveryPermitRecord)
def consume(permit_id: str, payload: RecoveryPermitConsume):
    try:
        return service.consume(permit_id, payload)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)):
    return service.audit(workspace_id)
