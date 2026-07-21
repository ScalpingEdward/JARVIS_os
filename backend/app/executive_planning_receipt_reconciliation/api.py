from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from .models import (
    PlanningReceiptAudit,
    PlanningReceiptCreate,
    PlanningReceiptExecuteRequest,
    PlanningReceiptRecord,
    PlanningReceiptStatus,
)
from .service import planning_receipt_reconciliation_service


router = APIRouter(
    prefix="/v1/executive-planning-receipt-reconciliation",
    tags=["executive-planning-receipt-reconciliation"],
)


@router.get("/status", response_model=PlanningReceiptStatus)
def status(workspace_id: str = Query(min_length=1)) -> PlanningReceiptStatus:
    return planning_receipt_reconciliation_service.status(workspace_id)


@router.post("/records", response_model=PlanningReceiptRecord)
def create_record(payload: PlanningReceiptCreate) -> PlanningReceiptRecord:
    try:
        return planning_receipt_reconciliation_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[PlanningReceiptRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[PlanningReceiptRecord]:
    return planning_receipt_reconciliation_service.list_records(workspace_id)


@router.get("/records/{record_id}", response_model=PlanningReceiptRecord)
def get_record(record_id: UUID, workspace_id: str = Query(min_length=1)) -> PlanningReceiptRecord:
    record = planning_receipt_reconciliation_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="planning receipt record not found")
    return record


@router.post("/records/{record_id}/execute", response_model=PlanningReceiptRecord)
def execute_record(
    record_id: UUID,
    payload: PlanningReceiptExecuteRequest,
    workspace_id: str = Query(min_length=1),
) -> PlanningReceiptRecord:
    try:
        return planning_receipt_reconciliation_service.execute(record_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[PlanningReceiptAudit])
def audit(workspace_id: str = Query(min_length=1)) -> list[PlanningReceiptAudit]:
    return planning_receipt_reconciliation_service.audit_records(workspace_id)
