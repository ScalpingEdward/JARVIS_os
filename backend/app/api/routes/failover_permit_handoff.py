from fastapi import APIRouter, HTTPException, Query

from app.schemas.failover_permit_handoff import (
    FailoverPermitAction,
    FailoverPermitConsume,
    FailoverPermitCreate,
    FailoverPermitRecord,
)
from app.services.failover_permit_handoff import failover_permit_handoff_service as service


router = APIRouter(prefix="/v1/failover-permit-handoff", tags=["failover-permit-handoff"])


@router.get("/status")
def status():
    return service.status()


@router.post("/records", response_model=FailoverPermitRecord)
def create_record(payload: FailoverPermitCreate):
    try:
        return service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[FailoverPermitRecord])
def list_records(workspace_id: str = Query(min_length=1)):
    return service.list(workspace_id)


@router.get("/records/{permit_id}", response_model=FailoverPermitRecord)
def get_record(permit_id: str, workspace_id: str = Query(min_length=1)):
    try:
        return service.get(workspace_id, permit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{permit_id}/actions", response_model=FailoverPermitRecord)
def act(permit_id: str, payload: FailoverPermitAction):
    try:
        return service.act(
            payload.workspace_id,
            permit_id,
            payload.action,
            payload.actor,
            payload.operation_id,
            payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/records/{permit_id}/consume", response_model=FailoverPermitRecord)
def consume(permit_id: str, payload: FailoverPermitConsume):
    try:
        return service.consume(permit_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)):
    return service.audit(workspace_id)
