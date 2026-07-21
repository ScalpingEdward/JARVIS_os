from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, PendingOrderAssessment, PendingOrderAssessmentCreate, PendingOrderExecuteRequest, PendingOrderStatus
from .service import pending_order_oco_service

router = APIRouter(tags=["executive-mt5-pending-order-oco"])


@router.get("/v1/executive-mt5-pending-orders/status", response_model=PendingOrderStatus)
def pending_order_status(workspace_id: str = Query(min_length=1, max_length=100)) -> PendingOrderStatus:
    return pending_order_oco_service.status(workspace_id)


@router.post("/v1/executive-mt5-pending-orders/assessments", response_model=PendingOrderAssessment, status_code=status.HTTP_201_CREATED)
def create_pending_order_assessment(payload: PendingOrderAssessmentCreate) -> PendingOrderAssessment:
    try:
        return pending_order_oco_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-pending-orders/assessments", response_model=list[PendingOrderAssessment])
def list_pending_order_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[PendingOrderAssessment]:
    return pending_order_oco_service.list_records(workspace_id)


@router.get("/v1/executive-mt5-pending-orders/assessments/{record_id}", response_model=PendingOrderAssessment)
def get_pending_order_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> PendingOrderAssessment:
    record = pending_order_oco_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Pending-order assessment not found")
    return record


@router.post("/v1/executive-mt5-pending-orders/assessments/{record_id}/execute", response_model=PendingOrderAssessment)
def execute_pending_order(record_id: UUID, request: PendingOrderExecuteRequest, workspace_id: str = Query(min_length=1, max_length=100)) -> PendingOrderAssessment:
    try:
        return pending_order_oco_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-pending-orders/audit", response_model=list[AuditRecord])
def pending_order_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return pending_order_oco_service.audit_records(workspace_id)
