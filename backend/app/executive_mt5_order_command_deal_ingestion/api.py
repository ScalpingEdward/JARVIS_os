from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, DispatchRequest, MT5ExecutionCreate, MT5ExecutionRecord, MT5ExecutionStatusResponse
from .service import executive_mt5_order_command_deal_ingestion_service

router = APIRouter(tags=["executive-mt5-order-command-deal-ingestion"])


@router.get("/v1/executive-mt5-order-execution/status", response_model=MT5ExecutionStatusResponse)
def execution_status(workspace_id: str = Query(min_length=1, max_length=100)) -> MT5ExecutionStatusResponse:
    return executive_mt5_order_command_deal_ingestion_service.status(workspace_id)


@router.post("/v1/executive-mt5-order-execution/assessments", response_model=MT5ExecutionRecord, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: MT5ExecutionCreate) -> MT5ExecutionRecord:
    try:
        return executive_mt5_order_command_deal_ingestion_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-order-execution/assessments", response_model=list[MT5ExecutionRecord])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[MT5ExecutionRecord]:
    return executive_mt5_order_command_deal_ingestion_service.list_records(workspace_id)


@router.get("/v1/executive-mt5-order-execution/assessments/{record_id}", response_model=MT5ExecutionRecord)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> MT5ExecutionRecord:
    record = executive_mt5_order_command_deal_ingestion_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="MT5 execution assessment not found")
    return record


@router.post("/v1/executive-mt5-order-execution/dispatch", response_model=MT5ExecutionRecord)
def dispatch(request: DispatchRequest) -> MT5ExecutionRecord:
    try:
        return executive_mt5_order_command_deal_ingestion_service.dispatch(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-order-execution/audit", response_model=list[AuditRecord])
def execution_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_mt5_order_command_deal_ingestion_service.audit(workspace_id)
