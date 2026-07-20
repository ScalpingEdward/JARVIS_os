from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ExecutionAssessment, ExecutionAssessmentCreate, ExecutionStatusResponse, ReconcileRequest
from .service import executive_order_execution_service

router = APIRouter(tags=["executive-order-execution"])


@router.get("/v1/executive-order-execution/status", response_model=ExecutionStatusResponse)
def execution_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutionStatusResponse:
    return executive_order_execution_service.status(workspace_id)


@router.post("/v1/executive-order-execution/executions", response_model=ExecutionAssessment, status_code=status.HTTP_201_CREATED)
def create_execution(payload: ExecutionAssessmentCreate) -> ExecutionAssessment:
    try:
        return executive_order_execution_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-order-execution/executions", response_model=list[ExecutionAssessment])
def list_executions(workspace_id: str = Query(min_length=1, max_length=100)) -> list[ExecutionAssessment]:
    return executive_order_execution_service.list_executions(workspace_id)


@router.get("/v1/executive-order-execution/executions/{record_id}", response_model=ExecutionAssessment)
def get_execution(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutionAssessment:
    record = executive_order_execution_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Order execution not found")
    return record


@router.post("/v1/executive-order-execution/reconcile", response_model=ExecutionAssessment)
def reconcile_execution(request: ReconcileRequest) -> ExecutionAssessment:
    try:
        return executive_order_execution_service.reconcile(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-order-execution/audit", response_model=list[AuditRecord])
def execution_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_order_execution_service.audit_records(workspace_id)
