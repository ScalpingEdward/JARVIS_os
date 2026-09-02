from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    LiveOrderAudit,
    LiveOrderCreate,
    LiveOrderExecuteRequest,
    LiveOrderRecord,
    LiveOrderStatus,
    RemoteExecutionReport,
)
from .service import live_order_executor_service

router = APIRouter(prefix="/v1/executive-mt5-live-order-executor", tags=["executive-mt5-live-order-executor"])


@router.get("/status", response_model=LiveOrderStatus)
def module_status(workspace_id: str = Query(min_length=1, max_length=100)) -> LiveOrderStatus:
    return live_order_executor_service.status(workspace_id)


@router.post("/orders", response_model=LiveOrderRecord, status_code=status.HTTP_201_CREATED)
def create_order(payload: LiveOrderCreate) -> LiveOrderRecord:
    try:
        return live_order_executor_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/orders", response_model=list[LiveOrderRecord])
def list_orders(workspace_id: str = Query(min_length=1, max_length=100)) -> list[LiveOrderRecord]:
    return live_order_executor_service.list_records(workspace_id)


@router.get("/orders/pending-execution", response_model=list[LiveOrderRecord])
def pending_execution(workspace_id: str = Query(min_length=1, max_length=100)) -> list[LiveOrderRecord]:
    """Orders already fully checked and human-approved, waiting for a
    remote execution agent (real MetaTrader5, on the machine with the
    terminal) to actually submit them. Registered before /orders/{record_id}
    deliberately -- otherwise FastAPI would try to parse "pending-execution"
    as a UUID."""
    return live_order_executor_service.pending_execution(workspace_id)


@router.get("/orders/{record_id}", response_model=LiveOrderRecord)
def get_order(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> LiveOrderRecord:
    record = live_order_executor_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Live order record not found")
    return record


@router.post("/orders/{record_id}/execute", response_model=LiveOrderRecord)
def execute_order(record_id: UUID, request: LiveOrderExecuteRequest, workspace_id: str = Query(min_length=1, max_length=100)) -> LiveOrderRecord:
    try:
        return live_order_executor_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/orders/{record_id}/report-execution", response_model=LiveOrderRecord)
def report_execution(
    record_id: UUID, report: RemoteExecutionReport, workspace_id: str = Query(min_length=1, max_length=100)
) -> LiveOrderRecord:
    """Called by the remote execution agent after it actually calls
    order_send() on the real MetaTrader5 terminal. Only accepted for a
    record currently PREFLIGHT_READY -- an already-executed, blocked, or
    cancelled record cannot be re-reported."""
    try:
        return live_order_executor_service.report_execution(record_id, workspace_id, report)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[LiveOrderAudit])
def order_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[LiveOrderAudit]:
    return live_order_executor_service.audit_records(workspace_id)
