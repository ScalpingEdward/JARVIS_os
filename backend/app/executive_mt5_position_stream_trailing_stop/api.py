from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, PositionStreamCreate, PositionStreamRecord, PositionStreamStatusResponse, TrailingModifyRequest
from .service import executive_mt5_position_stream_trailing_stop_service

router = APIRouter(tags=["executive-mt5-position-stream-trailing-stop"])


@router.get("/v1/executive-mt5-position-stream/status", response_model=PositionStreamStatusResponse)
def stream_status(workspace_id: str = Query(min_length=1, max_length=100)) -> PositionStreamStatusResponse:
    return executive_mt5_position_stream_trailing_stop_service.status(workspace_id)


@router.post("/v1/executive-mt5-position-stream/assessments", response_model=PositionStreamRecord, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: PositionStreamCreate) -> PositionStreamRecord:
    try:
        return executive_mt5_position_stream_trailing_stop_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-position-stream/assessments", response_model=list[PositionStreamRecord])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[PositionStreamRecord]:
    return executive_mt5_position_stream_trailing_stop_service.list_records(workspace_id)


@router.get("/v1/executive-mt5-position-stream/assessments/{record_id}", response_model=PositionStreamRecord)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> PositionStreamRecord:
    record = executive_mt5_position_stream_trailing_stop_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Position stream assessment not found")
    return record


@router.post("/v1/executive-mt5-position-stream/execute", response_model=PositionStreamRecord)
def execute_trailing(request: TrailingModifyRequest) -> PositionStreamRecord:
    try:
        return executive_mt5_position_stream_trailing_stop_service.execute(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-position-stream/audit", response_model=list[AuditRecord])
def stream_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_mt5_position_stream_trailing_stop_service.audit_records(workspace_id)
