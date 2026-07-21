from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, BridgeStartRequest, MT5RuntimeBridgeCreate, MT5RuntimeBridgeRecord, MT5RuntimeBridgeStatusResponse
from .service import executive_mt5_runtime_bridge_service

router = APIRouter(tags=["executive-mt5-runtime-bridge"])


@router.get("/v1/executive-mt5-runtime-bridge/status", response_model=MT5RuntimeBridgeStatusResponse)
def bridge_status(workspace_id: str = Query(min_length=1, max_length=100)) -> MT5RuntimeBridgeStatusResponse:
    return executive_mt5_runtime_bridge_service.status(workspace_id)


@router.post("/v1/executive-mt5-runtime-bridge/assessments", response_model=MT5RuntimeBridgeRecord, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: MT5RuntimeBridgeCreate) -> MT5RuntimeBridgeRecord:
    try:
        return executive_mt5_runtime_bridge_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-runtime-bridge/assessments", response_model=list[MT5RuntimeBridgeRecord])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[MT5RuntimeBridgeRecord]:
    return executive_mt5_runtime_bridge_service.list_records(workspace_id)


@router.get("/v1/executive-mt5-runtime-bridge/assessments/{record_id}", response_model=MT5RuntimeBridgeRecord)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> MT5RuntimeBridgeRecord:
    record = executive_mt5_runtime_bridge_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="MT5 runtime bridge assessment not found")
    return record


@router.post("/v1/executive-mt5-runtime-bridge/start", response_model=MT5RuntimeBridgeRecord)
def start_bridge(request: BridgeStartRequest) -> MT5RuntimeBridgeRecord:
    try:
        return executive_mt5_runtime_bridge_service.start_bridge(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-runtime-bridge/audit", response_model=list[AuditRecord])
def bridge_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_mt5_runtime_bridge_service.audit(workspace_id)
