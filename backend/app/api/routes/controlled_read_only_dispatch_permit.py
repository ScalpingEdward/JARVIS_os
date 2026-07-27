from fastapi import APIRouter, HTTPException, Query

from app.schemas.controlled_read_only_dispatch_permit import (
    DispatchPermitAction,
    DispatchPermitConsume,
    DispatchPermitCreate,
    DispatchPermitRecord,
)
from app.services.controlled_read_only_dispatch_permit import (
    controlled_read_only_dispatch_permit_service as service,
)

router = APIRouter(prefix="/v1/read-only-dispatch-permits", tags=["read-only-dispatch-permits"])


@router.get("/status")
def status():
    return service.status()


@router.post("/records", response_model=DispatchPermitRecord)
def create_record(payload: DispatchPermitCreate):
    try:
        return service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[DispatchPermitRecord])
def list_records(workspace_id: str = Query(min_length=1)):
    return service.list(workspace_id)


@router.get("/records/{permit_id}", response_model=DispatchPermitRecord)
def get_record(permit_id: str, workspace_id: str = Query(min_length=1)):
    try:
        return service.get(workspace_id, permit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{permit_id}/actions", response_model=DispatchPermitRecord)
def act(permit_id: str, payload: DispatchPermitAction):
    try:
        return service.act(permit_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/records/{permit_id}/consume", response_model=DispatchPermitRecord)
def consume(permit_id: str, payload: DispatchPermitConsume):
    try:
        return service.consume(permit_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)):
    return service.audit(workspace_id)
