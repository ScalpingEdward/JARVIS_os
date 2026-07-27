from fastapi import APIRouter, HTTPException, Query

from app.schemas.one_time_permit_dispatch_reconciliation import (
    DispatchHandoffCreate,
    DispatchReceipt,
    DispatchReconciliationAction,
    DispatchReconciliationRecord,
)
from app.services.one_time_permit_dispatch_reconciliation import (
    one_time_permit_dispatch_reconciliation_service as service,
)

router = APIRouter(
    prefix="/v1/permit-dispatch-reconciliation",
    tags=["permit-dispatch-reconciliation"],
)


@router.get("/status")
def status():
    return service.status()


@router.post("/records", response_model=DispatchReconciliationRecord)
def create_record(payload: DispatchHandoffCreate):
    try:
        return service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[DispatchReconciliationRecord])
def list_records(workspace_id: str = Query(min_length=1)):
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=DispatchReconciliationRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)):
    try:
        return service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=DispatchReconciliationRecord)
def act(record_id: str, payload: DispatchReconciliationAction):
    try:
        return service.act(
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


@router.post("/records/{record_id}/receipt", response_model=DispatchReconciliationRecord)
def reconcile_receipt(record_id: str, payload: DispatchReceipt):
    try:
        return service.reconcile(record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)):
    return service.audit(workspace_id)
