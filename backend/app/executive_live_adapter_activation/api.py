from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import ActivationRequest, ActivationStatusResponse, AuditRecord, LiveAdapterActivationCreate, LiveAdapterActivationRecord
from .service import executive_live_adapter_activation_service

router = APIRouter(tags=["executive-live-adapter-activation"])


@router.get("/v1/executive-live-adapter-activation/status", response_model=ActivationStatusResponse)
def activation_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ActivationStatusResponse:
    return executive_live_adapter_activation_service.status(workspace_id)


@router.post("/v1/executive-live-adapter-activation/assessments", response_model=LiveAdapterActivationRecord, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: LiveAdapterActivationCreate) -> LiveAdapterActivationRecord:
    try:
        return executive_live_adapter_activation_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-live-adapter-activation/assessments", response_model=list[LiveAdapterActivationRecord])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[LiveAdapterActivationRecord]:
    return executive_live_adapter_activation_service.list_records(workspace_id)


@router.get("/v1/executive-live-adapter-activation/assessments/{record_id}", response_model=LiveAdapterActivationRecord)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> LiveAdapterActivationRecord:
    record = executive_live_adapter_activation_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Activation assessment not found")
    return record


@router.post("/v1/executive-live-adapter-activation/activate", response_model=LiveAdapterActivationRecord)
def activate(request: ActivationRequest) -> LiveAdapterActivationRecord:
    try:
        return executive_live_adapter_activation_service.activate(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-live-adapter-activation/audit", response_model=list[AuditRecord])
def activation_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_live_adapter_activation_service.audit(workspace_id)
