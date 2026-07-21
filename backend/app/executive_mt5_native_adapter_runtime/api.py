from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    NativeAdapterAssessment,
    NativeAdapterAssessmentCreate,
    NativeAdapterAuditRecord,
    NativeAdapterExecuteRequest,
    NativeAdapterListResponse,
    NativeAdapterStatusResponse,
)
from .service import native_adapter_runtime_service

router = APIRouter(tags=["executive-mt5-native-adapter-runtime"])


@router.get("/v1/executive-mt5-native-adapter/status", response_model=NativeAdapterStatusResponse)
def adapter_status(workspace_id: str = Query(min_length=1, max_length=100)) -> NativeAdapterStatusResponse:
    return native_adapter_runtime_service.status(workspace_id)


@router.post(
    "/v1/executive-mt5-native-adapter/assessments",
    response_model=NativeAdapterAssessment,
    status_code=status.HTTP_201_CREATED,
)
def create_assessment(payload: NativeAdapterAssessmentCreate) -> NativeAdapterAssessment:
    try:
        return native_adapter_runtime_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-native-adapter/assessments", response_model=NativeAdapterListResponse)
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> NativeAdapterListResponse:
    items = native_adapter_runtime_service.list_records(workspace_id)
    return NativeAdapterListResponse(items=items, count=len(items))


@router.get("/v1/executive-mt5-native-adapter/assessments/{record_id}", response_model=NativeAdapterAssessment)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> NativeAdapterAssessment:
    record = native_adapter_runtime_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Native adapter assessment not found")
    return record


@router.post("/v1/executive-mt5-native-adapter/assessments/{record_id}/execute", response_model=NativeAdapterAssessment)
def execute_assessment(
    record_id: UUID,
    request: NativeAdapterExecuteRequest,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> NativeAdapterAssessment:
    try:
        return native_adapter_runtime_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-native-adapter/audit", response_model=list[NativeAdapterAuditRecord])
def adapter_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[NativeAdapterAuditRecord]:
    return native_adapter_runtime_service.audit_records(workspace_id)
